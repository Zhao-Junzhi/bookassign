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

from label_construct.client import LLMClient, merge_usage
from label_construct.io_utils import (
    build_logger,
    copy_json_file,
    ensure_results_tree,
    get_final_samples_dir,
    get_runs_dir,
    get_selected_sample_map,
    get_variable_label_path,
    iter_sample_paths,
    resolve_results_dir_for_model,
    set_results_root_for_model,
    to_project_relative,
    write_json,
)
from label_construct.method_review import run_method_review
from label_construct.variable_extract import run_variable_extraction
from label_construct.variable_finalize import run_variable_finalize


ALLOWED_STAGES = {"method_review", "variable_extract", "variable_finalize"}
DEFAULT_MODEL = "gpt-4o"
TOKEN_IN_MILLION = 1_000_000


def parse_stages(raw: str) -> list[str]:
    stages = [stage.strip() for stage in raw.split(",") if stage.strip()]
    if not stages:
        raise ValueError("至少需要一个 stage")
    unknown = [stage for stage in stages if stage not in ALLOWED_STAGES]
    if unknown:
        raise ValueError(f"不支持的 stage: {', '.join(unknown)}")
    return stages


async def verify_model_access(model: str, logger) -> None:
    client = LLMClient(model=model, logger=logger)
    await client.chat('只返回严格 JSON：{"ok":1}')


def _extract_stage_usage(stage_summary: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(stage_summary, dict):
        return merge_usage()
    return merge_usage(stage_summary.get("token_usage"))


def build_pipeline_token_usage(summary: dict[str, Any]) -> dict[str, Any]:
    variable_extract_summary = summary.get("variable_extract")
    if not isinstance(variable_extract_summary, dict):
        variable_extract_summary = {}

    method_review_usage = _extract_stage_usage(summary.get("method_review"))
    variable_extract_major_usage = _extract_stage_usage(variable_extract_summary.get("major"))
    variable_extract_suggest_usage = _extract_stage_usage(variable_extract_summary.get("suggest"))
    variable_finalize_usage = _extract_stage_usage(summary.get("variable_finalize"))

    first_pass_usage = merge_usage(
        method_review_usage,
        variable_extract_major_usage,
        variable_extract_suggest_usage,
        variable_finalize_usage,
    )

    return {
        "method_review": method_review_usage,
        "variable_extract_major_round_0": variable_extract_major_usage,
        "variable_extract_suggest_round_0": variable_extract_suggest_usage,
        "variable_finalize": variable_finalize_usage,
        "first_pass_total": first_pass_usage,
    }


def _format_tokens_in_millions(value: Any) -> str:
    try:
        token_count = int(value)
    except (TypeError, ValueError):
        token_count = 0
    return f"{token_count / TOKEN_IN_MILLION:.6f}M"


def emit_pipeline_token_usage(summary: dict[str, Any]) -> None:
    major_model = str(summary.get("model_major", "unknown"))
    suggest_model = str(summary.get("model_suggest", "unknown"))
    token_usage = summary.get("token_usage")
    if not isinstance(token_usage, dict):
        return

    stage_labels = {
        "method_review": f"run_method_review（{major_model}）",
        "variable_extract_major_round_0": f"run_variable_extraction_round_0_major（{major_model}）",
        "variable_extract_suggest_round_0": f"run_variable_extraction_round_0_suggest（{suggest_model}）",
        "variable_finalize": f"run_variable_finalize（{major_model}）",
        "first_pass_total": "first_pass_total",
    }

    for stage_key, stage_name in stage_labels.items():
        stage_usage = token_usage.get(stage_key)
        if not isinstance(stage_usage, dict):
            continue
        print(
            f"{stage_name}："
            f"prompt_tokens={_format_tokens_in_millions(stage_usage.get('prompt_tokens'))}, "
            f"total_tokens={_format_tokens_in_millions(stage_usage.get('total_tokens'))}, "
            f"request_count={int(stage_usage.get('request_count', 0) or 0)}"
        )


async def _run_round0_variable_extraction(
    sample_paths: list[Path],
    model: str,
    force: bool,
    max_workers: int,
) -> dict[str, Any]:
    set_results_root_for_model(model, default_model=DEFAULT_MODEL)
    ensure_results_tree()
    return await run_variable_extraction(
        sample_paths=sample_paths,
        model=model,
        round_index=0,
        force=force,
        max_workers=max_workers,
    )


def _copy_major_round0_to_final(sample_paths: list[Path], logger) -> dict[str, Any]:
    final_samples_dir = get_final_samples_dir()
    final_samples_dir.mkdir(parents=True, exist_ok=True)

    copied_count = 0
    failures = []
    for sample_path in sample_paths:
        sample_key = sample_path.stem
        round0_path = get_variable_label_path(sample_key, 0)
        if not round0_path.exists():
            failures.append(
                {
                    "sample_key": sample_key,
                    "error": f"缺少 major round_0 变量标签: {to_project_relative(round0_path)}",
                }
            )
            continue

        copy_json_file(round0_path, final_samples_dir / f"{sample_key}.json")
        copied_count += 1

    logger.info("未提供 suggest 模型，已将 major round_0 结果复制到 final/samples: copied=%s", copied_count)
    return {
        "mode": "copy_major_round0",
        "output_dir": to_project_relative(final_samples_dir.parent),
        "samples_dir": to_project_relative(final_samples_dir),
        "copied_count": copied_count,
        "failed_count": len(failures),
        "failures": failures,
        "token_usage": merge_usage(),
    }


async def run_pipeline(args) -> dict[str, object]:
    set_results_root_for_model(args.model_major, default_model=DEFAULT_MODEL)
    ensure_results_tree()
    logger = build_logger("run_pipeline")
    stages = parse_stages(args.stages)
    sample_paths = iter_sample_paths(limit=args.limit)
    selected_map = get_selected_sample_map(sample_paths)
    has_suggest_model = bool(args.model_suggest)
    effective_stages = [stage for stage in stages if has_suggest_model or stage != "variable_finalize"]

    summary: dict[str, object] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_major": args.model_major,
        "model_suggest": args.model_suggest,
        "major_results_dir": to_project_relative(resolve_results_dir_for_model(args.model_major, DEFAULT_MODEL)),
        "suggest_results_dir": (
            to_project_relative(resolve_results_dir_for_model(args.model_suggest, DEFAULT_MODEL))
            if has_suggest_model
            else ""
        ),
        "stages": effective_stages,
        "limit": args.limit,
        "force": args.force,
        "sample_count": len(sample_paths),
        "sample_keys": list(selected_map.keys()),
    }

    logger.info(
        "流水线开始: major=%s, suggest=%s, stages=%s, sample_count=%s, force=%s",
        args.model_major,
        args.model_suggest,
        effective_stages,
        len(sample_paths),
        args.force,
    )

    needs_variable_base = "variable_extract" in effective_stages or "variable_finalize" in effective_stages

    try:
        if sample_paths:
            await verify_model_access(args.model_major, logger)
            if has_suggest_model and args.model_suggest != args.model_major:
                await verify_model_access(args.model_suggest, logger)

        if "method_review" in effective_stages:
            set_results_root_for_model(args.model_major, default_model=DEFAULT_MODEL)
            summary["method_review"] = await run_method_review(
                sample_paths=sample_paths,
                model=args.model_major,
                force=args.force,
                max_workers=args.max_workers,
            )

        if needs_variable_base:
            variable_extract_summary = {
                "major": await _run_round0_variable_extraction(
                    sample_paths=sample_paths,
                    model=args.model_major,
                    force=args.force,
                    max_workers=args.max_workers,
                )
            }
            if has_suggest_model:
                variable_extract_summary["suggest"] = await _run_round0_variable_extraction(
                    sample_paths=sample_paths,
                    model=args.model_suggest,
                    force=args.force,
                    max_workers=args.max_workers,
                )
            summary["variable_extract"] = variable_extract_summary

        if "variable_finalize" in effective_stages:
            set_results_root_for_model(args.model_major, default_model=DEFAULT_MODEL)
            summary["variable_finalize"] = await run_variable_finalize(
                sample_paths=sample_paths,
                major_model=args.model_major,
                suggest_model=args.model_suggest,
                force=args.force,
                max_workers=args.max_workers,
            )
        elif needs_variable_base and not has_suggest_model:
            set_results_root_for_model(args.model_major, default_model=DEFAULT_MODEL)
            summary["final_outputs"] = _copy_major_round0_to_final(sample_paths, logger)

        summary["status"] = "completed"
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = str(exc)
        logger.exception("流水线执行失败: major=%s, suggest=%s", args.model_major, args.model_suggest)
    finally:
        set_results_root_for_model(args.model_major, default_model=DEFAULT_MODEL)
        summary["token_usage"] = build_pipeline_token_usage(summary)
        summary_path = get_runs_dir() / "summary.json"
        write_json(summary_path, summary)
        logger.info("流水线摘要已写入 %s", to_project_relative(summary_path))

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the label construction pipeline for book1_r2.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N samples by numeric sample id.")
    parser.add_argument(
        "--stages",
        type=str,
        default="method_review,variable_extract,variable_finalize",
        help="Comma-separated stages: method_review,variable_extract,variable_finalize",
    )
    parser.add_argument("--model_major", type=str, required=True, help="Major model name.")
    parser.add_argument("--model_suggest", type=str, default=None, help="Suggest model name. If omitted, skip variable finalize.")
    parser.add_argument("--force", action="store_true", help="Recompute outputs even if existing results are found.")
    parser.add_argument("--max-workers", type=int, default=5, help="Concurrent request count.")
    args = parser.parse_args()

    summary = asyncio.run(run_pipeline(args))
    emit_pipeline_token_usage(summary)
    if summary.get("status") != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
