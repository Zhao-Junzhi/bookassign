#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from label_construct.client import LLMClient
from label_construct.io_utils import (
    build_logger,
    build_variable_label_record,
    ensure_results_tree,
    get_variable_label_path,
    iter_sample_paths,
    load_json,
    to_project_relative,
    validate_variable_payload,
    write_json,
)
from label_construct.prompts import build_variable_extract_prompt


DEFAULT_MAX_WORKERS = 5


async def _process_sample(
    sample_path: Path,
    round_index: int,
    semaphore: asyncio.Semaphore,
    client: LLMClient,
    logger,
) -> tuple[str, dict[str, Any], bool, str | None]:
    async with semaphore:
        sample = load_json(sample_path)
        try:
            variables = await client.generate_json(build_variable_extract_prompt(sample))
            variables = validate_variable_payload(variables)
            record = build_variable_label_record(sample, sample_path, round_index, variables)
            return sample_path.stem, record, False, None
        except Exception as exc:
            logger.warning("变量抽取失败 %s，已回退为 {}: %s", sample_path.name, exc)
            fallback_record = build_variable_label_record(sample, sample_path, round_index, {})
            return sample_path.stem, fallback_record, True, str(exc)


async def run_variable_extraction(
    sample_paths: list[Path],
    model: str,
    round_index: int = 0,
    force: bool = False,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, Any]:
    ensure_results_tree()
    logger = build_logger(f"variable_extract_round_{round_index}")

    cached_samples = 0
    pending_paths = []
    for sample_path in sample_paths:
        output_path = get_variable_label_path(sample_path.stem, round_index)
        if output_path.exists() and not force:
            cached_samples += 1
        else:
            pending_paths.append(sample_path)

    logger.info(
        "变量抽取开始: round=%s, 样本=%s, 缓存命中=%s, 待处理=%s",
        round_index,
        len(sample_paths),
        cached_samples,
        len(pending_paths),
    )

    successes = 0
    fallback_samples = []

    if pending_paths:
        semaphore = asyncio.Semaphore(max_workers)
        client = LLMClient(model=model, logger=logger)
        tasks = [_process_sample(path, round_index, semaphore, client, logger) for path in pending_paths]

        for index, coro in enumerate(asyncio.as_completed(tasks), start=1):
            sample_key, record, used_fallback, error = await coro
            write_json(get_variable_label_path(sample_key, round_index), record)
            successes += 1
            if used_fallback:
                fallback_samples.append({"sample_key": sample_key, "reason": error})

            if index % 10 == 0 or index == len(tasks):
                logger.info("变量抽取进度: round=%s, %s/%s", round_index, index, len(tasks))

    output_dir = get_variable_label_path("dummy", round_index).parent
    logger.info("变量抽取结果目录: %s", to_project_relative(output_dir))

    return {
        "round": round_index,
        "output_dir": to_project_relative(output_dir),
        "selected_samples": len(sample_paths),
        "processed_samples": len(pending_paths),
        "cached_samples": cached_samples,
        "success_count": cached_samples + successes,
        "fallback_count": len(fallback_samples),
        "fallback_samples": fallback_samples,
        "failed_count": 0,
        "failures": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract variables used by the answer for book1_r2 samples.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model name to use for this stage.")
    parser.add_argument("--round", type=int, default=0, dest="round_index", help="Label round index.")
    parser.add_argument("--force", action="store_true", help="Recompute JSON outputs even if they already exist.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Concurrent request count.")
    args = parser.parse_args()

    sample_paths = iter_sample_paths(limit=args.limit)
    asyncio.run(
        run_variable_extraction(
            sample_paths=sample_paths,
            model=args.model,
            round_index=args.round_index,
            force=args.force,
            max_workers=args.max_workers,
        )
    )


if __name__ == "__main__":
    main()
