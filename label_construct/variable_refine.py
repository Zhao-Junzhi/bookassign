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
    get_variable_review_path,
    iter_sample_paths,
    load_csv_rows,
    load_json,
    normalize_flag,
    parse_json_cell,
    to_project_relative,
    validate_variable_payload,
    write_json,
)
from label_construct.prompts import build_variable_refine_prompt


DEFAULT_MAX_WORKERS = 5


def _load_review_rows(source_round: int) -> dict[str, dict[str, Any]]:
    rows = {}
    for row in load_csv_rows(get_variable_review_path(source_round)):
        sample_key = row.get("sample_key")
        if not sample_key:
            continue
        rows[sample_key] = {
            "sample_key": sample_key,
            "round": row.get("round", source_round),
            "is_accurate": normalize_flag(row.get("is_accurate", 0)),
            "missing_variables": parse_json_cell(row.get("missing_variables", "")),
            "redundant_variables": parse_json_cell(row.get("redundant_variables", "")),
            "incorrect_fields": parse_json_cell(row.get("incorrect_fields", "")),
            "reason": row.get("reason", ""),
            "revision_advice": row.get("revision_advice", ""),
        }
    return rows


async def _process_sample(
    sample_path: Path,
    target_round: int,
    review_row: dict[str, Any],
    semaphore: asyncio.Semaphore,
    client: LLMClient,
    logger,
) -> tuple[str, dict[str, Any] | None, str | None]:
    async with semaphore:
        try:
            sample = load_json(sample_path)
            previous_record = load_json(get_variable_label_path(sample_path.stem, target_round - 1))
            variables = await client.generate_json(
                build_variable_refine_prompt(sample, previous_record, review_row, target_round)
            )
            variables = validate_variable_payload(variables)
            record = build_variable_label_record(sample, sample_path, target_round, variables)
            return sample_path.stem, record, None
        except Exception as exc:
            logger.error("变量修正失败 %s round=%s: %s", sample_path.name, target_round, exc)
            return sample_path.stem, None, str(exc)


async def run_variable_refine(
    sample_paths: list[Path],
    model: str,
    target_round: int,
    force: bool = False,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, Any]:
    if target_round < 1:
        raise ValueError("target_round 必须从 1 开始")

    ensure_results_tree()
    logger = build_logger(f"variable_refine_round_{target_round}")
    review_rows = _load_review_rows(target_round - 1)

    pending_paths = []
    cached_samples = 0
    for sample_path in sample_paths:
        sample_key = sample_path.stem
        review_row = review_rows.get(sample_key)
        if review_row is None:
            raise FileNotFoundError(f"缺少审阅结果: {to_project_relative(get_variable_review_path(target_round - 1))}")
        if review_row["is_accurate"] == 1:
            continue

        output_path = get_variable_label_path(sample_key, target_round)
        if output_path.exists() and not force:
            cached_samples += 1
        else:
            pending_paths.append(sample_path)

    logger.info(
        "变量修正开始: round=%s, 样本=%s, 缓存命中=%s, 待处理=%s",
        target_round,
        len(sample_paths),
        cached_samples,
        len(pending_paths),
    )

    successes = 0
    failures = []

    if pending_paths:
        semaphore = asyncio.Semaphore(max_workers)
        client = LLMClient(model=model, logger=logger)
        tasks = [
            _process_sample(path, target_round, review_rows[path.stem], semaphore, client, logger)
            for path in pending_paths
        ]

        for index, coro in enumerate(asyncio.as_completed(tasks), start=1):
            sample_key, record, error = await coro
            if record is not None:
                write_json(get_variable_label_path(sample_key, target_round), record)
                successes += 1
            else:
                failures.append({"sample_key": sample_key, "error": error})

            if index % 10 == 0 or index == len(tasks):
                logger.info("变量修正进度: round=%s, %s/%s", target_round, index, len(tasks))

    output_dir = get_variable_label_path("dummy", target_round).parent
    logger.info("变量修正结果目录: %s", to_project_relative(output_dir))

    return {
        "round": target_round,
        "output_dir": to_project_relative(output_dir),
        "selected_samples": len(sample_paths),
        "processed_samples": len(pending_paths),
        "cached_samples": cached_samples,
        "success_count": cached_samples + successes,
        "success_sample_keys": sorted(
            [
                path.stem
                for path in sample_paths
                if get_variable_label_path(path.stem, target_round).exists()
            ],
            key=int,
        ),
        "failed_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine extracted variables using review feedback.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model name to use for this stage.")
    parser.add_argument("--round", type=int, required=True, dest="target_round", help="Write refined labels into round_N.")
    parser.add_argument("--force", action="store_true", help="Recompute JSON outputs even if they already exist.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Concurrent request count.")
    args = parser.parse_args()

    sample_paths = iter_sample_paths(limit=args.limit)
    asyncio.run(
        run_variable_refine(
            sample_paths=sample_paths,
            model=args.model,
            target_round=args.target_round,
            force=args.force,
            max_workers=args.max_workers,
        )
    )


if __name__ == "__main__":
    main()
