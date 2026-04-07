#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
import tempfile
import unittest
from pathlib import Path

from label_construct.client import extract_json_from_text
from label_construct import io_utils
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
        old_pipeline_variable_labels_dir = pipeline_module.VARIABLE_LABELS_DIR

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_root = Path(tmpdir)
                io_utils.PROJECT_ROOT = temp_root
                io_utils.VARIABLE_LABELS_DIR = temp_root / "variable_labels"
                pipeline_module.VARIABLE_LABELS_DIR = io_utils.VARIABLE_LABELS_DIR

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
            pipeline_module.VARIABLE_LABELS_DIR = old_pipeline_variable_labels_dir


if __name__ == "__main__":
    unittest.main()
