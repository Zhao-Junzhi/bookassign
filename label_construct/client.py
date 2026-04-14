#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import openai

from api_info import api_key, base_url


DEFAULT_MODEL = "gpt-4o"


class APIError(RuntimeError):
    """Raised when the LLM request fails after retries."""


class LLMResponseFormatError(ValueError):
    """Raised when model output cannot be parsed while preserving usage."""

    def __init__(self, message: str, usage: dict[str, int]) -> None:
        super().__init__(message)
        self.usage = usage


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "request_count": self.request_count,
        }


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def extract_usage(response: Any) -> LLMUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return LLMUsage()
    return LLMUsage(
        prompt_tokens=_coerce_int(getattr(usage, "prompt_tokens", 0)),
        completion_tokens=_coerce_int(getattr(usage, "completion_tokens", 0)),
        total_tokens=_coerce_int(getattr(usage, "total_tokens", 0)),
        request_count=1,
    )


def merge_usage(*usage_items: dict[str, Any] | LLMUsage | None) -> dict[str, int]:
    merged = LLMUsage()
    for item in usage_items:
        if item is None:
            continue
        current = item.to_dict() if isinstance(item, LLMUsage) else item
        merged.prompt_tokens += _coerce_int(current.get("prompt_tokens"))
        merged.completion_tokens += _coerce_int(current.get("completion_tokens"))
        merged.total_tokens += _coerce_int(current.get("total_tokens"))
        merged.request_count += _coerce_int(current.get("request_count"))
    return merged.to_dict()


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
            next_char = repaired[index + 1] if index + 1 < len(repaired) else ""
            if next_char in {"\"", "\\", "/", "b", "f", "n", "r", "t"}:
                chars.append(char)
                escaped = True
                continue
            if next_char == "u" and index + 5 < len(repaired):
                hex_part = repaired[index + 2 : index + 6]
                if re.fullmatch(r"[0-9a-fA-F]{4}", hex_part):
                    chars.append(char)
                    escaped = True
                    continue
            chars.append("\\\\")
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

    async def chat_with_usage(self, prompt: str) -> tuple[str, dict[str, int]]:
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
                return content, extract_usage(response).to_dict()
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

    async def chat(self, prompt: str) -> str:
        content, _ = await self.chat_with_usage(prompt)
        return content

    async def generate_json_with_usage(self, prompt: str) -> tuple[Any, dict[str, int]]:
        content, usage = await self.chat_with_usage(prompt)
        try:
            return extract_json_from_text(content), usage
        except ValueError as exc:
            raise LLMResponseFormatError(str(exc), usage) from exc

    async def generate_json(self, prompt: str) -> Any:
        result, _ = await self.generate_json_with_usage(prompt)
        return result
