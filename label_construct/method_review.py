#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
import re
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
    get_input_dir,
    get_method_review_dir,
    iter_sample_paths,
    load_existing_rows_by_key,
    load_json,
    resolve_final_results_dir,
    sample_sort_key,
    set_input_dir,
    set_results_root,
    to_project_relative,
    write_csv,
)
from label_construct.prompts import METHOD_TAXONOMY_TEXT, build_method_review_prompt


DEFAULT_MAX_WORKERS = 5
METHOD_PATH_PATTERN = re.compile(r"^[^\\]+\\[^\\]+$")
TAXONOMY_PARENT_PATTERN = re.compile(r'-\s*[“"]([^”"]+)[”"]部分包括：\[(.*?)\]\。?')
TAXONOMY_ITEM_PATTERN = re.compile(r'[“"]([^”"]+)[”"]')


def _build_secondary_to_parent_map() -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for parent_name, raw_children in TAXONOMY_PARENT_PATTERN.findall(METHOD_TAXONOMY_TEXT):
        for child_name in TAXONOMY_ITEM_PATTERN.findall(raw_children):
            mapping.setdefault(child_name.strip(), set()).add(parent_name.strip())
    return mapping


SECONDARY_TO_PARENT_MAP = _build_secondary_to_parent_map()


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: sample_sort_key(Path(f"{row['sample_key']}.json")))


def _is_current_method_row(row: dict[str, Any]) -> bool:
    return "current_method" not in row and "is_consistent" not in row and "needs_new_category" not in row


def _is_full_method_path(value: str) -> bool:
    return bool(METHOD_PATH_PATTERN.fullmatch((value or "").strip()))


def _normalize_suggested_method(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized or _is_full_method_path(normalized):
        return normalized

    parent_names = SECONDARY_TO_PARENT_MAP.get(normalized, set())
    if len(parent_names) == 1:
        parent_name = next(iter(parent_names))
        return f"{parent_name}\\{normalized}"
    return normalized


def _has_cacheable_suggested_method(row: dict[str, Any]) -> bool:
    suggested_method = _normalize_suggested_method(str(row.get("suggested_method", "") or ""))
    row["suggested_method"] = suggested_method
    return bool(suggested_method) and _is_full_method_path(suggested_method)


def _should_use_cached_method_row(row: dict[str, Any], update_method: bool) -> bool:
    if not update_method:
        return True
    return _has_cacheable_suggested_method(row)


def _load_current_method_rows(output_path: Path, force: bool) -> dict[str, dict[str, str]]:
    all_current_rows = {
        sample_key: row
        for sample_key, row in load_existing_rows_by_key(output_path).items()
        if _is_current_method_row(row)
    }
    if not force:
        for row in all_current_rows.values():
            row["suggested_method"] = _normalize_suggested_method(str(row.get("suggested_method", "") or ""))
    return all_current_rows


def normalize_method_review_cache(force: bool = False) -> dict[str, Any]:
    ensure_results_tree()
    logger = build_logger("method_review")
    output_path = get_method_review_dir() / "method_review.csv"
    all_current_rows = _load_current_method_rows(output_path, force=force)
    merged_rows = _sort_rows(list(all_current_rows.values()))
    write_csv(output_path, METHOD_REVIEW_FIELDNAMES, merged_rows)
    logger.info("方法审阅缓存预处理已写入 %s", to_project_relative(output_path))
    cacheable_count = sum(_has_cacheable_suggested_method(dict(row)) for row in all_current_rows.values())
    return {
        "output_csv": to_project_relative(output_path),
        "row_count": len(merged_rows),
        "cacheable_count": cacheable_count,
        "token_usage": merge_usage(),
    }


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

            suggested_method = str(result.get("suggested_method", "") or "").strip()
            proposed_new_category = str(result.get("proposed_new_category", "") or "").strip()
            reason = str(result.get("reason", "") or "").strip()
            if proposed_new_category:
                suggested_method = ""
            else:
                suggested_method = _normalize_suggested_method(suggested_method)
                if not suggested_method:
                    raise ValueError("方法标注结果缺少 suggested_method")
                if not _is_full_method_path(suggested_method):
                    raise ValueError("方法标注结果 suggested_method 必须为“一级类目\\二级类目”格式")

            row = {
                "sample_key": str(sample.get("sample_key", sample_path.stem)),
                "case_id": sample.get("case_id", ""),
                "suggested_method": suggested_method,
                "proposed_new_category": proposed_new_category,
                "reason": reason,
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
    update_method: bool = True,
) -> dict[str, Any]:
    ensure_results_tree()
    logger = build_logger("method_review")
    output_path = get_method_review_dir() / "method_review.csv"
    all_current_rows = _load_current_method_rows(output_path, force=force)
    existing_rows = {} if force else {
        sample_key: row
        for sample_key, row in all_current_rows.items()
        if _should_use_cached_method_row(row, update_method=update_method)
    }

    cached_rows = []
    pending_paths = []
    for sample_path in sample_paths:
        sample_key = sample_path.stem
        if not force and sample_key in existing_rows:
            cached_rows.append(existing_rows[sample_key])
        else:
            pending_paths.append(sample_path)

    logger.info("方法审阅开始: 样本=%s, 缓存命中=%s, 待处理=%s", len(sample_paths), len(cached_rows), len(pending_paths))

    results_by_key = {} if force else dict(all_current_rows)
    failures = []
    usage_summary = merge_usage()

    if pending_paths:
        semaphore = asyncio.Semaphore(max_workers)
        client = LLMClient(model=model, logger=logger)
        tasks = [_process_sample(path, semaphore, client, logger) for path in pending_paths]

        for index, coro in enumerate(asyncio.as_completed(tasks), start=1):
            sample_key, row, error, usage = await coro
            if row is not None:
                results_by_key[sample_key] = row
                usage_summary = merge_usage(usage_summary, usage)
            else:
                failures.append({"sample_key": sample_key, "error": error})

            if index % 10 == 0 or index == len(tasks):
                logger.info("方法审阅进度: %s/%s", index, len(tasks))

    merged_rows = _sort_rows(list(results_by_key.values()))
    write_csv(output_path, METHOD_REVIEW_FIELDNAMES, merged_rows)
    logger.info("方法审阅结果已写入 %s", to_project_relative(output_path))

    return {
        "output_csv": to_project_relative(output_path),
        "selected_samples": len(sample_paths),
        "processed_samples": len(pending_paths),
        "cached_samples": len(cached_rows),
        "update_method": update_method,
        "success_count": len(merged_rows),
        "failed_count": len(failures),
        "failures": failures,
        "token_usage": usage_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Select method taxonomy labels for book1_r2 samples.")
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Sample directory name or path, for example book1_r3. Used to locate label_construct/results_final/<dir>.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model name to use for this stage.")
    parser.add_argument("--force", action="store_true", help="Recompute rows even if the CSV already contains them.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Concurrent request count.")
    parser.add_argument(
        "--update_method",
        type=lambda value: str(value).strip().lower() in {"1", "true", "yes", "y"},
        default=True,
        help="Whether to require suggested_method to be a non-empty 一级类目\\二级类目 path for cache hits. Use false to cache by sample_key only.",
    )
    parser.add_argument(
        "--normalize-cache-only",
        action="store_true",
        help="Only normalize existing method_review.csv entries to 一级类目\\二级类目 format; never call LLM.",
    )
    args = parser.parse_args()

    if args.input_dir:
        input_dir = Path(args.input_dir)
        if not input_dir.is_absolute():
            input_dir = Path(__file__).resolve().parent.parent / input_dir
        input_dir = input_dir.resolve()
        set_input_dir(input_dir)
        set_results_root(resolve_final_results_dir(input_dir))
    else:
        set_input_dir(get_input_dir())

    if args.normalize_cache_only:
        normalize_method_review_cache(force=args.force)
        return

    sample_paths = iter_sample_paths(limit=args.limit)
    asyncio.run(
        run_method_review(
            sample_paths=sample_paths,
            model=args.model,
            force=args.force,
            max_workers=args.max_workers,
            update_method=args.update_method,
        )
    )


if __name__ == "__main__":
    main()
