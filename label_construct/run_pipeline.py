#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from label_construct.client import LLMClient
from label_construct.io_utils import (
    build_logger,
    copy_json_file,
    ensure_results_tree,
    get_final_review_path,
    get_final_samples_dir,
    get_results_dir,
    get_runs_dir,
    get_variable_review_path,
    get_selected_sample_map,
    iter_sample_paths,
    latest_existing_label_path,
    latest_review_round,
    results_dir_name_for_model,
    set_results_root_for_model,
    load_csv_rows,
    normalize_flag,
    to_project_relative,
    VARIABLE_REVIEW_FIELDNAMES,
    write_csv,
    write_json,
)
from label_construct.method_review import run_method_review
from label_construct.variable_extract import run_variable_extraction
from label_construct.variable_refine import run_variable_refine
from label_construct.variable_review import run_variable_review


ALLOWED_STAGES = {"method_review", "variable_extract", "variable_iterate"}
DEFAULT_MODEL = "gpt-4o"


def parse_stages(raw: str) -> list[str]:
    stages = [stage.strip() for stage in raw.split(",") if stage.strip()]
    if not stages:
        raise ValueError("至少需要一个 stage")
    unknown = [stage for stage in stages if stage not in ALLOWED_STAGES]
    if unknown:
        raise ValueError(f"不支持的 stage: {', '.join(unknown)}")
    return stages


def _load_inaccurate_keys(round_index: int, selected_map: dict[str, Path]) -> list[str]:
    inaccurate = []
    for row in load_csv_rows(get_variable_review_path(round_index)):
        sample_key = row.get("sample_key", "")
        if sample_key in selected_map and normalize_flag(row.get("is_accurate", 0)) == 0:
            inaccurate.append(sample_key)
    return sorted(inaccurate, key=lambda sample_key: int(sample_key))


def _next_pending_paths(
    inaccurate_keys: list[str],
    refine_summary: dict[str, object],
    selected_map: dict[str, Path],
) -> tuple[list[Path], list[str]]:
    success_keys = {
        str(sample_key)
        for sample_key in refine_summary.get("success_sample_keys", [])
    }
    dropped_keys = [sample_key for sample_key in inaccurate_keys if sample_key not in success_keys]
    next_paths = [selected_map[sample_key] for sample_key in inaccurate_keys if sample_key in success_keys]
    return next_paths, dropped_keys


def parse_models(raw_models: list[str] | None) -> list[str]:
    if not raw_models:
        return [DEFAULT_MODEL]
    models: list[str] = []
    for item in raw_models:
        for model_name in item.split(","):
            cleaned = model_name.strip()
            if cleaned:
                models.append(cleaned)
    return models or [DEFAULT_MODEL]


async def verify_model_access(model: str, logger) -> None:
    client = LLMClient(model=model, logger=logger)
    await client.chat('只返回严格 JSON：{"ok":1}')


def sync_final_outputs(sample_paths: list[Path], max_rounds: int, logger) -> dict[str, object]:
    final_dir = get_results_dir() / "variable_labels" / "final"
    final_samples_dir = get_final_samples_dir()
    final_samples_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing_samples = []
    final_rounds = {}
    final_review_rows = []
    missing_reviews = []

    for sample_path in sample_paths:
        sample_key = sample_path.stem
        latest_path = latest_existing_label_path(sample_key, max_rounds)
        if latest_path is None:
            missing_samples.append(sample_key)
            continue

        target_path = final_samples_dir / f"{sample_key}.json"
        copy_json_file(latest_path, target_path)
        copied += 1

        round_name = latest_path.parent.parent.name
        if round_name.startswith("round_"):
            final_round = int(round_name.split("_", 1)[1])
        else:
            final_round = round_name
        final_rounds[sample_key] = final_round

        latest_review = latest_review_round(sample_key, max_rounds)
        if latest_review is None:
            missing_reviews.append(sample_key)
            continue

        for row in load_csv_rows(get_variable_review_path(latest_review)):
            if row.get("sample_key") == sample_key:
                final_review_rows.append(row)
                break

    final_review_rows = sorted(final_review_rows, key=lambda row: int(row["sample_key"]))
    write_csv(get_final_review_path(), VARIABLE_REVIEW_FIELDNAMES, final_review_rows)

    logger.info(
        "final 汇总完成: copied=%s, missing_samples=%s, review_rows=%s, missing_reviews=%s",
        copied,
        len(missing_samples),
        len(final_review_rows),
        len(missing_reviews),
    )
    return {
        "output_dir": to_project_relative(final_dir),
        "samples_dir": to_project_relative(final_samples_dir),
        "review_csv": to_project_relative(get_final_review_path()),
        "copied_count": copied,
        "missing_sample_keys": missing_samples,
        "review_row_count": len(final_review_rows),
        "missing_review_sample_keys": missing_reviews,
        "final_rounds": final_rounds,
    }


async def run_pipeline_for_model(args, model: str) -> dict[str, object]:
    set_results_root_for_model(model, default_model=DEFAULT_MODEL)
    ensure_results_tree()
    logger = build_logger("run_pipeline")
    stages = parse_stages(args.stages)
    sample_paths = iter_sample_paths(limit=args.limit)
    selected_map = get_selected_sample_map(sample_paths)

    summary: dict[str, object] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "results_dir": to_project_relative(get_results_dir()),
        "stages": stages,
        "limit": args.limit,
        "max_rounds": args.max_rounds,
        "force": args.force,
        "sample_count": len(sample_paths),
        "sample_keys": list(selected_map.keys()),
    }

    logger.info(
        "流水线开始: model=%s, results_dir=%s, stages=%s, sample_count=%s, force=%s",
        model,
        results_dir_name_for_model(model, DEFAULT_MODEL),
        stages,
        len(sample_paths),
        args.force,
    )

    if sample_paths:
        await verify_model_access(model, logger)

    if "method_review" in stages:
        summary["method_review"] = await run_method_review(
            sample_paths=sample_paths,
            model=model,
            force=args.force,
            max_workers=args.max_workers,
        )

    needs_variable_base = "variable_extract" in stages or "variable_iterate" in stages
    if needs_variable_base:
        summary["variable_extract"] = await run_variable_extraction(
            sample_paths=sample_paths,
            model=model,
            round_index=0,
            force=args.force,
            max_workers=args.max_workers,
        )

    if "variable_iterate" in stages:
        pending_paths = list(sample_paths)
        round_summaries = []
        current_round = 0

        while True:
            if not pending_paths:
                logger.info("变量迭代提前结束: 没有待修正样本")
                break

            review_summary = await run_variable_review(
                sample_paths=pending_paths,
                model=model,
                round_index=current_round,
                force=args.force,
                max_workers=args.max_workers,
            )

            inaccurate_keys = _load_inaccurate_keys(current_round, selected_map)
            round_entry: dict[str, object] = {
                "round": current_round,
                "review": review_summary,
                "inaccurate_sample_keys": inaccurate_keys,
            }

            if not inaccurate_keys:
                round_summaries.append(round_entry)
                logger.info("变量迭代在 round %s 的审阅后停止: 当前样本均准确", current_round)
                break

            if current_round >= args.max_rounds:
                round_summaries.append(round_entry)
                logger.info("变量迭代在 round %s 的审阅后停止: 已达到最大修正轮数", current_round)
                break

            next_round = current_round + 1
            pending_paths = [selected_map[key] for key in inaccurate_keys]
            refine_summary = await run_variable_refine(
                sample_paths=pending_paths,
                model=model,
                target_round=next_round,
                force=args.force,
                max_workers=args.max_workers,
            )
            round_entry["refine"] = refine_summary
            pending_paths, dropped_keys = _next_pending_paths(inaccurate_keys, refine_summary, selected_map)
            if dropped_keys:
                logger.warning(
                    "以下样本在 round=%s 修正失败，已从后续审阅中跳过: %s",
                    next_round,
                    ",".join(dropped_keys),
                )
                round_entry["dropped_sample_keys"] = dropped_keys
            round_summaries.append(round_entry)
            current_round = next_round

        summary["variable_iterate"] = round_summaries

    if needs_variable_base:
        summary["final_outputs"] = sync_final_outputs(sample_paths, args.max_rounds, logger)

    summary_path = get_runs_dir() / "summary.json"
    write_json(summary_path, summary)
    logger.info("流水线摘要已写入 %s", to_project_relative(summary_path))
    return summary


async def run_all_models(args) -> dict[str, Any]:
    models = parse_models(args.model)
    overall = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "models": models,
        "results": [],
        "failures": [],
    }

    for model in models:
        try:
            summary = await run_pipeline_for_model(args, model)
            overall["results"].append(
                {
                    "model": model,
                    "results_dir": summary.get("results_dir"),
                    "summary_path": summary.get("results_dir", "") + "/runs/summary.json",
                }
            )
        except Exception as exc:
            error_message = str(exc)
            print(f"[ERROR] model={model} 运行失败: {error_message}")
            overall["failures"].append({"model": model, "error": error_message})
            continue

    return overall


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the label construction pipeline for book1_r2.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum refinement rounds for variable correction.")
    parser.add_argument(
        "--stages",
        type=str,
        default="method_review,variable_extract,variable_iterate",
        help="Comma-separated stages: method_review,variable_extract,variable_iterate",
    )
    parser.add_argument(
        "--model",
        nargs="+",
        default=[DEFAULT_MODEL],
        help="One or more model names. Multiple values will be processed sequentially.",
    )
    parser.add_argument("--force", action="store_true", help="Recompute outputs even if existing results are found.")
    parser.add_argument("--max-workers", type=int, default=5, help="Concurrent request count.")
    args = parser.parse_args()

    asyncio.run(run_all_models(args))


if __name__ == "__main__":
    main()
