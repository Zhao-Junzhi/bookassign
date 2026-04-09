#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import openai

from api_info import api_key, base_url


DEFAULT_MODEL = "gpt-4o"


class APIError(RuntimeError):
    """Raised when the LLM request fails after retries."""


def extract_json_from_text(content: str) -> Any:
    """Extract the first valid JSON object or array from model output."""
    if content is None:
        raise ValueError("模型输出为空")

    text = content.strip()
    if not text:
        raise ValueError("模型输出为空字符串")

    fenced_blocks = []
    segments = text.split("```")
    for index in range(1, len(segments), 2):
        block = segments[index].strip()
        if block.startswith("json"):
            block = block[4:].strip()
        fenced_blocks.append(block)

    candidates = fenced_blocks + [text]
    decoder = json.JSONDecoder()

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        repaired_candidate = repair_json_like_text(candidate)
        if repaired_candidate != candidate:
            try:
                return json.loads(repaired_candidate)
            except json.JSONDecodeError:
                pass

        for pos, char in enumerate(candidate):
            if char not in "{[":
                continue
            try:
                parsed, end = decoder.raw_decode(candidate[pos:])
                trailing = candidate[pos + end :].strip()
                if trailing and not trailing.startswith("```"):
                    continue
                return parsed
            except json.JSONDecodeError:
                continue

        for pos, char in enumerate(repaired_candidate):
            if char not in "{[":
                continue
            try:
                parsed, end = decoder.raw_decode(repaired_candidate[pos:])
                trailing = repaired_candidate[pos + end :].strip()
                if trailing and not trailing.startswith("```"):
                    continue
                return parsed
            except json.JSONDecodeError:
                continue

    preview = text[:200].replace("\n", "\\n")
    raise ValueError(f"无法从模型输出中解析JSON: {preview}...")


def repair_json_like_text(text: str) -> str:
    """Best-effort repair for common model JSON formatting mistakes."""
    if not text:
        return text

    repaired = text.strip()

    # Remove code fence language headers accidentally preserved in slices.
    if repaired.startswith("json\n"):
        repaired = repaired[5:]

    # Remove trailing commas before object/array close.
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

    chars: list[str] = []
    in_string = False
    escaped = False
    expecting_key = False
    stack: list[str] = []

    def next_non_space(index: int) -> str:
        cursor = index + 1
        while cursor < len(repaired) and repaired[cursor].isspace():
            cursor += 1
        if cursor >= len(repaired):
            return ""
        return repaired[cursor]

    for index, char in enumerate(repaired):
        if not in_string:
            chars.append(char)
            if char == "{":
                stack.append("{")
                expecting_key = True
            elif char == "[":
                stack.append("[")
                expecting_key = False
            elif char == "}":
                if stack:
                    stack.pop()
                expecting_key = False
            elif char == "]":
                if stack:
                    stack.pop()
                expecting_key = False
            elif char == ",":
                expecting_key = bool(stack and stack[-1] == "{")
            elif char == ":":
                expecting_key = False
            elif char == "\"":
                in_string = True
            continue

        if escaped:
            chars.append(char)
            escaped = False
            continue

        if char == "\\":
            chars.append(char)
            escaped = True
            continue

        if char == "\"":
            following = next_non_space(index)
            is_closing_quote = following in {",", "}", "]", ":", ""}
            if is_closing_quote:
                chars.append(char)
                in_string = False
                if expecting_key and following == ":":
                    expecting_key = False
            else:
                chars.append("\\\"")
            continue

        if char == "\n":
            chars.append("\\n")
            continue

        if char == "\r":
            chars.append("\\r")
            continue

        if char == "\t":
            chars.append("\\t")
            continue

        chars.append(char)

    return "".join(chars)


class LLMClient:
    """Shared async OpenAI client with retry and rate-limit handling."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
        timeout: int = 120,
        max_retries: int = 3,
        rate_limit: float = 0.5,
        logger: logging.Logger | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        self.logger = logger or logging.getLogger(__name__)
        self._client = openai.AsyncClient(api_key=api_key, base_url=base_url)
        self._rate_lock = asyncio.Lock()
        self._last_call_started_at = 0.0

    async def _wait_for_rate_limit(self) -> None:
        if self.rate_limit <= 0:
            return

        async with self._rate_lock:
            now = time.monotonic()
            delay = self.rate_limit - (now - self._last_call_started_at)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_call_started_at = time.monotonic()

    async def chat(self, prompt: str) -> str:
        for attempt in range(self.max_retries):
            try:
                await self._wait_for_rate_limit()
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    timeout=self.timeout,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise APIError("模型返回为空")
                return content
            except Exception as exc:  # pragma: no cover - exercised in integration only
                message = str(exc)
                if "rate limit" in message.lower():
                    wait_time = (attempt + 1) * 2
                    self.logger.warning("API限流，等待%s秒后重试", wait_time)
                    await asyncio.sleep(wait_time)
                    continue
                if "timeout" in message.lower():
                    self.logger.warning("API超时，第%s次重试", attempt + 1)
                    await asyncio.sleep(2)
                    continue
                self.logger.error("API调用异常: %s", exc)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                raise APIError(f"API调用失败: {exc}") from exc

        raise APIError("超过最大重试次数")

    async def generate_json(self, prompt: str) -> Any:
        content = await self.chat(prompt)
        return extract_json_from_text(content)
