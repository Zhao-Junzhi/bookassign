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
    VARIABLE_REVIEW_FIELDNAMES,
    build_logger,
    ensure_results_tree,
    get_variable_label_path,
    get_variable_review_path,
    iter_sample_paths,
    load_existing_rows_by_key,
    load_json,
    normalize_flag,
    sample_sort_key,
    to_project_relative,
    write_csv,
)
from label_construct.prompts import build_variable_review_prompt


DEFAULT_MAX_WORKERS = 5


def build_fallback_review_row(sample_key: str, round_index: int, reason: str) -> dict[str, Any]:
    return {
        "sample_key": sample_key,
        "round": round_index,
        "is_accurate": 0,
        "missing_variables": [],
        "redundant_variables": [],
        "incorrect_fields": [],
        "reason": reason,
        "revision_advice": "审阅阶段未能产出可解析结果。请重新检查该样本的变量提取结果，并根据 answer 补全或修正变量。",
    }


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: sample_sort_key(Path(f"{row['sample_key']}.json")))


async def _process_sample(
    sample_path: Path,
    round_index: int,
    semaphore: asyncio.Semaphore,
    client: LLMClient,
    logger,
) -> tuple[str, dict[str, Any] | None, str | None]:
    async with semaphore:
        sample_key = sample_path.stem
        try:
            sample = load_json(sample_path)
            variable_path = get_variable_label_path(sample_key, round_index)
            variable_record = load_json(variable_path)
            result = await client.generate_json(build_variable_review_prompt(sample, variable_record, round_index))
            if not isinstance(result, dict):
                raise ValueError("变量审阅输出必须是JSON对象")

            row = {
                "sample_key": str(sample.get("sample_key", sample_key)),
                "round": round_index,
                "is_accurate": normalize_flag(result.get("is_accurate", 0)),
                "missing_variables": result.get("missing_variables", []),
                "redundant_variables": result.get("redundant_variables", []),
                "incorrect_fields": result.get("incorrect_fields", []),
                "reason": result.get("reason", ""),
                "revision_advice": result.get("revision_advice", ""),
            }
            return sample_key, row, None
        except Exception as exc:
            logger.warning("变量审阅失败 %s round=%s，已回退为不准确: %s", sample_path.name, round_index, exc)
            fallback_row = build_fallback_review_row(sample_key, round_index, f"审阅结果解析失败: {exc}")
            return sample_key, fallback_row, str(exc)


async def run_variable_review(
    sample_paths: list[Path],
    round_index: int,
    force: bool = False,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, Any]:
    if round_index < 0:
        raise ValueError("round_index 不能小于 0")

    ensure_results_tree()
    logger = build_logger(f"variable_review_round_{round_index}")
    output_path = get_variable_review_path(round_index)
    existing_rows = {} if force else load_existing_rows_by_key(output_path)

    cached_rows = []
    pending_paths = []
    fallback_rows = []
    for sample_path in sample_paths:
        sample_key = sample_path.stem
        if not force and sample_key in existing_rows:
            cached_rows.append(existing_rows[sample_key])
            continue

        current_round_path = get_variable_label_path(sample_key, round_index)
        if not current_round_path.exists():
            fallback_rows.append(
                build_fallback_review_row(
                    sample_key,
                    round_index,
                    f"缺少当前轮变量标签: {to_project_relative(current_round_path)}",
                )
            )
            logger.warning("变量审阅缺少当前轮变量标签 %s，已回退为不准确记录", to_project_relative(current_round_path))
            continue

        pending_paths.append(sample_path)

    logger.info(
        "变量审阅开始: round=%s, 样本=%s, 缓存命中=%s, 待处理=%s",
        round_index,
        len(sample_paths),
        len(cached_rows),
        len(pending_paths),
    )

    results = list(cached_rows) + list(fallback_rows)
    failures = []
    if pending_paths:
        semaphore = asyncio.Semaphore(max_workers)
        client = LLMClient(logger=logger)
        tasks = [_process_sample(path, round_index, semaphore, client, logger) for path in pending_paths]

        for index, coro in enumerate(asyncio.as_completed(tasks), start=1):
            sample_key, row, error = await coro
            results.append(row)
            if error is not None:
                failures.append({"sample_key": sample_key, "error": error})

            if index % 10 == 0 or index == len(tasks):
                logger.info("变量审阅进度: round=%s, %s/%s", round_index, index, len(tasks))

    merged_rows = _sort_rows(results)
    write_csv(output_path, VARIABLE_REVIEW_FIELDNAMES, merged_rows)
    logger.info("变量审阅结果已写入 %s", to_project_relative(output_path))

    accurate_count = 0
    for row in merged_rows:
        if normalize_flag(row.get("is_accurate", 0)) == 1:
            accurate_count += 1

    return {
        "round": round_index,
        "output_csv": to_project_relative(output_path),
        "selected_samples": len(sample_paths),
        "processed_samples": len(pending_paths),
        "cached_samples": len(cached_rows),
        "accurate_count": accurate_count,
        "fallback_count": len(fallback_rows) + len(failures),
        "failed_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Review extracted variables for book1_r2 samples.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument("--round", type=int, required=True, dest="round_index", help="Review the labels stored under round_N.")
    parser.add_argument("--force", action="store_true", help="Recompute CSV rows even if they already exist.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Concurrent request count.")
    args = parser.parse_args()

    sample_paths = iter_sample_paths(limit=args.limit)
    asyncio.run(
        run_variable_review(
            sample_paths=sample_paths,
            round_index=args.round_index,
            force=args.force,
            max_workers=args.max_workers,
        )
    )


if __name__ == "__main__":
    main()
