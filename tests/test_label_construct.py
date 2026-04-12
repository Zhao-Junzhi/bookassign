#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
import unittest
from types import ModuleType
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from label_construct.client import extract_json_from_text
from label_construct import io_utils

prompts_stub = ModuleType("label_construct.prompts")
prompts_stub.build_method_review_prompt = lambda sample: {}
prompts_stub.build_variable_extract_prompt = lambda sample: {}
prompts_stub.build_variable_extract_retry_prompt = lambda sample: {}
prompts_stub.build_variable_finalize_prompt = lambda **kwargs: {}
prompts_stub.build_variable_review_prompt = lambda *args, **kwargs: {}
sys.modules.setdefault("label_construct.prompts", prompts_stub)

import label_construct.run_pipeline as pipeline_module
from label_construct.variable_review import build_fallback_review_row


class LabelConstructTests(unittest.TestCase):
    def test_extract_json_from_text_handles_fenced_block(self) -> None:
        content = '模型说明\n```json\n{"a": 1, "b": [2, 3]}\n```\n补充说明'
        self.assertEqual(extract_json_from_text(content), {"a": 1, "b": [2, 3]})

    def test_extract_json_from_text_handles_wrapped_json(self) -> None:
        content = 'Result: {"is_consistent": 1, "reason": "ok"}'
        self.assertEqual(
            extract_json_from_text(content),
            {"is_consistent": 1, "reason": "ok"},
        )

    def test_iter_sample_paths_uses_numeric_sort(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            for name in ("10.json", "2.json", "1.json"):
                (temp_root / name).write_text("{}", encoding="utf-8")

            paths = io_utils.iter_sample_paths(sample_dir=temp_root)
            self.assertEqual([path.name for path in paths], ["1.json", "2.json", "10.json"])
            limited_paths = io_utils.iter_sample_paths(sample_dir=temp_root, limit=2)
            self.assertEqual([path.name for path in limited_paths], ["1.json", "2.json"])

    def test_results_dir_name_for_model(self) -> None:
        self.assertEqual(io_utils.results_dir_name_for_model("gpt-4o"), "results")
        self.assertEqual(io_utils.results_dir_name_for_model("gpt-5.2"), "results(gpt-5.2)")
        self.assertEqual(
            io_utils.results_dir_name_for_model("gemini 3/pro preview"),
            "results(gemini_3_pro_preview)",
        )

    def test_parse_models_supports_multiple_inputs(self) -> None:
        models = pipeline_module.parse_models(["gpt-4o", "gpt-5.2,claude-sonnet-4-6"])
        self.assertEqual(models, ["gpt-4o", "gpt-5.2", "claude-sonnet-4-6"])

    def test_validate_variable_payload_accepts_expected_schema(self) -> None:
        payload = {
            "X1": {
                "id": "X1",
                "value": [1, 2, 3],
                "class": "numerical",
                "role": "X",
                "description": "Predictor",
            },
            "Y1": {
                "id": "Y1",
                "value": [0, 1, 1],
                "class": "binary",
                "role": "Y",
                "description": "Outcome",
            },
        }
        self.assertEqual(io_utils.validate_variable_payload(payload), payload)

    def test_validate_variable_payload_rejects_missing_field(self) -> None:
        payload = {
            "X1": {
                "id": "X1",
                "value": [1, 2, 3],
                "class": "numerical",
                "role": "X",
            }
        }
        with self.assertRaises(ValueError):
            io_utils.validate_variable_payload(payload)

    def test_validate_variable_payload_normalizes_common_aliases(self) -> None:
        payload = {
            "n_d": {
                "id": "n_d",
                "value": 12,
                "class": "numeric",
                "role": "parameter",
                "description": "Sample size parameter.",
            }
        }
        normalized = io_utils.validate_variable_payload(payload)
        self.assertEqual(normalized["n_d"]["class"], "numerical")
        self.assertEqual(normalized["n_d"]["role"], "NR")

    def test_next_pending_paths_filters_failed_refinements(self) -> None:
        selected_map = {
            "1": Path("/tmp/1.json"),
            "2": Path("/tmp/2.json"),
            "3": Path("/tmp/3.json"),
        }
        next_paths, dropped = pipeline_module._next_pending_paths(
            inaccurate_keys=["1", "2", "3"],
            refine_summary={"success_sample_keys": ["1", "3"]},
            selected_map=selected_map,
        )
        self.assertEqual([path.name for path in next_paths], ["1.json", "3.json"])
        self.assertEqual(dropped, ["2"])

    def test_build_fallback_review_row_marks_sample_inaccurate(self) -> None:
        row = build_fallback_review_row("468", 0, "审阅结果解析失败")
        self.assertEqual(row["sample_key"], "468")
        self.assertEqual(row["round"], 0)
        self.assertEqual(row["is_accurate"], 0)
        self.assertIn("审阅阶段未能产出可解析结果", row["revision_advice"])

    def test_sync_final_outputs_collect_latest_samples_and_reviews(self) -> None:
        old_project_root = io_utils.PROJECT_ROOT
        old_variable_labels_dir = io_utils.VARIABLE_LABELS_DIR

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_root = Path(tmpdir)
                io_utils.PROJECT_ROOT = temp_root
                io_utils.VARIABLE_LABELS_DIR = temp_root / "variable_labels"

                sample_path = temp_root / "book1_r2" / "1.json"
                sample_path.parent.mkdir(parents=True, exist_ok=True)
                sample_path.write_text("{}", encoding="utf-8")

                round_0_path = io_utils.get_variable_label_path("1", 0)
                round_1_path = io_utils.get_variable_label_path("1", 1)
                io_utils.write_json(round_0_path, {"sample_key": "1", "round": 0})
                io_utils.write_json(round_1_path, {"sample_key": "1", "round": 1})
                io_utils.write_csv(
                    io_utils.get_variable_review_path(1),
                    io_utils.VARIABLE_REVIEW_FIELDNAMES,
                    [
                        {
                            "sample_key": "1",
                            "round": 1,
                            "is_accurate": 1,
                            "missing_variables": [],
                            "redundant_variables": [],
                            "incorrect_fields": [],
                            "reason": "ok",
                            "revision_advice": "无",
                        }
                    ],
                )

                summary = pipeline_module.sync_final_outputs(
                    [sample_path],
                    max_rounds=3,
                    logger=logging.getLogger("test"),
                )
                final_path = io_utils.get_final_samples_dir() / "1.json"
                final_review_path = io_utils.get_final_review_path()

                self.assertTrue(final_path.exists())
                self.assertTrue(final_review_path.exists())
                self.assertEqual(json.loads(final_path.read_text(encoding="utf-8"))["round"], 1)
                self.assertEqual(summary["copied_count"], 1)
                self.assertEqual(summary["final_rounds"]["1"], 1)
                self.assertEqual(io_utils.load_csv_rows(final_review_path)[0]["sample_key"], "1")
        finally:
            io_utils.PROJECT_ROOT = old_project_root
            io_utils.VARIABLE_LABELS_DIR = old_variable_labels_dir

    def test_parse_input_dirs_supports_multiple_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            book1 = temp_root / "book1_r3"
            book2 = temp_root / "book2_r3"
            book1.mkdir()
            book2.mkdir()

            parsed = pipeline_module.parse_input_dirs([str(book1), f"{book2}, {book1}"])
            self.assertEqual(parsed, [book1.resolve(), book2.resolve()])

    def test_run_pipeline_writes_results_under_results_final_per_input_dir(self) -> None:
        old_project_root = io_utils.PROJECT_ROOT
        old_input_dir = io_utils.get_input_dir()
        old_results_dir = io_utils.get_results_dir()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_root = Path(tmpdir)
                io_utils.PROJECT_ROOT = temp_root

                book1 = temp_root / "book1_r3"
                book2 = temp_root / "book2_r3"
                for folder in (book1, book2):
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / "1.json").write_text('{"sample_key":"1","case_id":"demo"}', encoding="utf-8")

                async def fake_verify_model_access(model: str, logger) -> None:
                    return None

                async def fake_run_method_review(sample_paths, model, force=False, max_workers=5):
                    output_path = io_utils.get_method_review_dir() / "method_review.csv"
                    io_utils.write_csv(
                        output_path,
                        io_utils.METHOD_REVIEW_FIELDNAMES,
                        [
                            {
                                "sample_key": sample_paths[0].stem,
                                "case_id": "demo",
                                "suggested_method": "regression",
                                "proposed_new_category": "",
                                "reason": "ok",
                            }
                        ],
                    )
                    return {"output_csv": io_utils.to_project_relative(output_path), "token_usage": {}}

                async def fake_run_round0_variable_extraction(
                    sample_paths,
                    model,
                    force,
                    max_workers,
                    output_root=None,
                    log_dir=None,
                ):
                    sample_key = sample_paths[0].stem
                    if output_root is None:
                        output_path = io_utils.get_variable_label_path(sample_key, 0)
                    else:
                        output_path = Path(output_root) / "round_0" / "samples" / f"{sample_key}.json"
                    io_utils.write_json(output_path, {"sample_key": sample_key, "variables": {}})
                    return {"output_dir": io_utils.to_project_relative(output_path.parent), "token_usage": {}}

                args = SimpleNamespace(
                    input_dirs=[str(book1), str(book2)],
                    limit=None,
                    stages="method_review,variable_extract",
                    model_major="gpt-4o",
                    model_suggest=None,
                    force=False,
                    max_workers=1,
                )

                with patch.object(pipeline_module, "verify_model_access", fake_verify_model_access), patch.object(
                    pipeline_module, "run_method_review", fake_run_method_review
                ), patch.object(
                    pipeline_module, "_run_round0_variable_extraction", fake_run_round0_variable_extraction
                ):
                    summary = asyncio.run(pipeline_module.run_pipeline(args))

                self.assertEqual(summary["status"], "completed")
                self.assertEqual(summary["run_count"], 2)

                for folder_name in ("book1_r3", "book2_r3"):
                    result_root = temp_root / "label_construct" / "results_final" / folder_name
                    self.assertTrue((result_root / "method_review" / "method_review.csv").exists())
                    self.assertTrue((result_root / "variable_labels" / "round_0" / "samples" / "1.json").exists())
                    self.assertTrue((result_root / "logs" / "run_pipeline.log").exists())
                    self.assertTrue((result_root / "runs" / "summary.json").exists())
        finally:
            io_utils.PROJECT_ROOT = old_project_root
            io_utils.set_input_dir(old_input_dir)
            io_utils.set_results_root(old_results_dir)


if __name__ == "__main__":
    unittest.main()
