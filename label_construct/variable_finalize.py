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
    VARIABLE_FINAL_REVIEW_FIELDNAMES,
    build_logger,
    build_variable_label_record,
    copy_json_file,
    ensure_results_tree,
    get_final_review_path,
    get_final_samples_dir,
    get_variable_label_path,
    get_variable_label_path_for_model,
    iter_sample_paths,
    load_existing_rows_by_key,
    load_json,
    normalize_flag,
    sample_sort_key,
    to_project_relative,
    validate_variable_payload,
    write_csv,
    write_json,
)
from label_construct.prompts import build_variable_finalize_prompt


DEFAULT_MAX_WORKERS = 5


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: sample_sort_key(Path(f"{row['sample_key']}.json")))


def _is_current_final_review_row(row: dict[str, Any]) -> bool:
    return "modify" in row and "round" not in row and "is_accurate" not in row


def _extract_revised_variables(result: dict[str, Any]) -> dict[str, Any]:
    for key in ("revised_variables", "adjusted_variables", "variables"):
        value = result.get(key)
        if isinstance(value, dict):
            return value
    raise ValueError("终审结果缺少 revised_variables")


async def _process_sample(
    sample_path: Path,
    major_model: str,
    suggest_model: str,
    semaphore: asyncio.Semaphore,
    client: LLMClient,
    logger,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None, str | None, dict[str, int] | None]:
    async with semaphore:
        sample_key = sample_path.stem
        try:
            sample = load_json(sample_path)
            major_record = load_json(get_variable_label_path(sample_key, 0))
            suggest_record = load_json(get_variable_label_path_for_model(suggest_model, sample_key, 0))
            result, usage = await client.generate_json_with_usage(
                build_variable_finalize_prompt(
                    sample=sample,
                    major_model=major_model,
                    major_variable_record=major_record,
                    suggest_model=suggest_model,
                    suggest_variable_record=suggest_record,
                )
            )
            if not isinstance(result, dict):
                raise ValueError("变量终审输出必须是JSON对象")

            modify = normalize_flag(result.get("modify", 0))
            reason = str(result.get("reason", "") or "").strip()
            review_row = {
                "sample_key": str(sample.get("sample_key", sample_key)),
                "modify": modify,
                "reason": reason,
            }

            final_record = None
            if modify == 1:
                revised_variables = validate_variable_payload(_extract_revised_variables(result))
                final_record = build_variable_label_record(sample, sample_path, "final", revised_variables)

            return sample_key, review_row, final_record, None, usage
        except Exception as exc:
            logger.warning("变量终审跳过样本 %s: %s", sample_path.name, exc)
            return sample_key, None, None, str(exc), getattr(exc, "usage", None)


async def run_variable_finalize(
    sample_paths: list[Path],
    major_model: str,
    suggest_model: str,
    force: bool = False,
    max_workers: int = DEFAULT_MAX_WORKERS,
    suggest_results_root: Path | None = None,
) -> dict[str, Any]:
    ensure_results_tree()
    logger = build_logger("variable_finalize")
    output_path = get_final_review_path()
    existing_rows = {} if force else {
        sample_key: row
        for sample_key, row in load_existing_rows_by_key(output_path).items()
        if _is_current_final_review_row(row)
    }
    final_samples_dir = get_final_samples_dir()
    final_samples_dir.mkdir(parents=True, exist_ok=True)

    cached_rows = []
    pending_paths = []
    failures = []
    for sample_path in sample_paths:
        sample_key = sample_path.stem
        major_round0_path = get_variable_label_path(sample_key, 0)
        suggest_round0_path = (
            Path(suggest_results_root).resolve() / "round_0" / "samples" / f"{sample_key}.json"
            if suggest_results_root is not None
            else get_variable_label_path_for_model(suggest_model, sample_key, 0)
        )
        if not major_round0_path.exists():
            failures.append(
                {
                    "sample_key": sample_key,
                    "error": f"缺少 major round_0 变量标签: {to_project_relative(major_round0_path)}",
                }
            )
            continue
        if not suggest_round0_path.exists():
            failures.append(
                {
                    "sample_key": sample_key,
                    "error": f"缺少 suggest round_0 变量标签: {to_project_relative(suggest_round0_path)}",
                }
            )
            continue

        final_sample_path = final_samples_dir / f"{sample_key}.json"
        if not force and sample_key in existing_rows and final_sample_path.exists():
            cached_rows.append(existing_rows[sample_key])
            continue

        pending_paths.append(sample_path)

    logger.info(
        "变量终审开始: 样本=%s, 缓存命中=%s, 待处理=%s",
        len(sample_paths),
        len(cached_rows),
        len(pending_paths),
    )

    results = list(cached_rows)
    usage_summary = merge_usage()
    modified_count = 0

    if pending_paths:
        semaphore = asyncio.Semaphore(max_workers)
        client = LLMClient(model=major_model, logger=logger)
        tasks = [
            _process_sample(path, major_model, suggest_model, semaphore, client, logger)
            for path in pending_paths
        ]

        for index, coro in enumerate(asyncio.as_completed(tasks), start=1):
            sample_key, row, final_record, error, sample_usage = await coro
            if row is not None:
                results.append(row)
                usage_summary = merge_usage(usage_summary, sample_usage)
                if normalize_flag(row.get("modify", 0)) == 1:
                    modified_count += 1
                    write_json(final_samples_dir / f"{sample_key}.json", final_record)
                else:
                    copy_json_file(get_variable_label_path(sample_key, 0), final_samples_dir / f"{sample_key}.json")
            else:
                failures.append({"sample_key": sample_key, "error": error})

            if index % 10 == 0 or index == len(tasks):
                logger.info("变量终审进度: %s/%s", index, len(tasks))

    merged_rows = _sort_rows(results)
    modified_count = sum(normalize_flag(row.get("modify", 0)) for row in merged_rows)
    write_csv(output_path, VARIABLE_FINAL_REVIEW_FIELDNAMES, merged_rows)
    logger.info("变量终审结果已写入 %s", to_project_relative(output_path))

    return {
        "output_dir": to_project_relative(final_samples_dir.parent),
        "samples_dir": to_project_relative(final_samples_dir),
        "review_csv": to_project_relative(output_path),
        "selected_samples": len(sample_paths),
        "processed_samples": len(pending_paths),
        "cached_samples": len(cached_rows),
        "modified_count": modified_count,
        "finalized_count": len(merged_rows),
        "failed_count": len(failures),
        "failures": failures,
        "token_usage": usage_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize variable labels using major/suggest model outputs.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument("--model-major", type=str, required=True, help="Major model name for final adjudication.")
    parser.add_argument("--model-suggest", type=str, required=True, help="Suggest model name for reference labels.")
    parser.add_argument("--force", action="store_true", help="Recompute outputs even if final outputs already exist.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Concurrent request count.")
    args = parser.parse_args()

    sample_paths = iter_sample_paths(limit=args.limit)
    asyncio.run(
        run_variable_finalize(
            sample_paths=sample_paths,
            major_model=args.model_major,
            suggest_model=args.model_suggest,
            force=args.force,
            max_workers=args.max_workers,
        )
    )


if __name__ == "__main__":
    main()
