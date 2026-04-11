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

from label_construct.client import LLMClient, merge_usage
from label_construct.io_utils import (
    METHOD_REVIEW_FIELDNAMES,
    build_logger,
    ensure_results_tree,
    get_method_review_dir,
    iter_sample_paths,
    load_existing_rows_by_key,
    load_json,
    normalize_flag,
    sample_sort_key,
    to_project_relative,
    write_csv,
)
from label_construct.prompts import build_method_review_prompt


DEFAULT_MAX_WORKERS = 5


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: sample_sort_key(Path(f"{row['sample_key']}.json")))


async def _process_sample(
    sample_path: Path,
    semaphore: asyncio.Semaphore,
    client: LLMClient,
    logger,
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, int] | None]:
    async with semaphore:
        try:
            sample = load_json(sample_path)
            result, usage = await client.generate_json_with_usage(build_method_review_prompt(sample))
            if not isinstance(result, dict):
                raise ValueError("方法审阅输出必须是JSON对象")

            current_method = sample.get("output", {}).get("method", "")
            is_consistent = normalize_flag(result.get("is_consistent", 0))
            suggested_method = result.get("suggested_method", "")
            if is_consistent and not suggested_method:
                suggested_method = current_method

            row = {
                "sample_key": str(sample.get("sample_key", sample_path.stem)),
                "case_id": sample.get("case_id", ""),
                "current_method": current_method,
                "is_consistent": is_consistent,
                "suggested_method": suggested_method,
                "needs_new_category": normalize_flag(result.get("needs_new_category", 0)),
                "proposed_new_category": result.get("proposed_new_category", ""),
                "reason": result.get("reason", ""),
            }
            return sample_path.stem, row, None, usage
        except Exception as exc:
            logger.warning("方法审阅跳过样本 %s: %s", sample_path.name, exc)
            return sample_path.stem, None, str(exc), getattr(exc, "usage", None)


async def run_method_review(
    sample_paths: list[Path],
    model: str,
    force: bool = False,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, Any]:
    ensure_results_tree()
    logger = build_logger("method_review")
    output_path = get_method_review_dir() / "method_review.csv"
    existing_rows = {} if force else load_existing_rows_by_key(output_path)

    cached_rows = []
    pending_paths = []
    for sample_path in sample_paths:
        sample_key = sample_path.stem
        if not force and sample_key in existing_rows:
            cached_rows.append(existing_rows[sample_key])
        else:
            pending_paths.append(sample_path)

    logger.info("方法审阅开始: 样本=%s, 缓存命中=%s, 待处理=%s", len(sample_paths), len(cached_rows), len(pending_paths))

    results = list(cached_rows)
    failures = []
    usage_summary = merge_usage()

    if pending_paths:
        semaphore = asyncio.Semaphore(max_workers)
        client = LLMClient(model=model, logger=logger)
        tasks = [_process_sample(path, semaphore, client, logger) for path in pending_paths]

        for index, coro in enumerate(asyncio.as_completed(tasks), start=1):
            sample_key, row, error, usage = await coro
            if row is not None:
                results.append(row)
                usage_summary = merge_usage(usage_summary, usage)
            else:
                failures.append({"sample_key": sample_key, "error": error})

            if index % 10 == 0 or index == len(tasks):
                logger.info("方法审阅进度: %s/%s", index, len(tasks))

    merged_rows = _sort_rows(results)
    write_csv(output_path, METHOD_REVIEW_FIELDNAMES, merged_rows)
    logger.info("方法审阅结果已写入 %s", to_project_relative(output_path))

    return {
        "output_csv": to_project_relative(output_path),
        "selected_samples": len(sample_paths),
        "processed_samples": len(pending_paths),
        "cached_samples": len(cached_rows),
        "success_count": len(merged_rows),
        "failed_count": len(failures),
        "failures": failures,
        "token_usage": usage_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Review output.method consistency for book1_r2 samples.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model name to use for this stage.")
    parser.add_argument("--force", action="store_true", help="Recompute rows even if the CSV already contains them.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Concurrent request count.")
    args = parser.parse_args()

    sample_paths = iter_sample_paths(limit=args.limit)
    asyncio.run(run_method_review(sample_paths=sample_paths, model=args.model, force=args.force, max_workers=args.max_workers))


if __name__ == "__main__":
    main()
