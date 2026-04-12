#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Iterable
import random


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "book1_r2"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "label_construct" / "results"
RESULTS_DIR = DEFAULT_RESULTS_DIR
METHOD_REVIEW_DIR = RESULTS_DIR / "method_review"
VARIABLE_LABELS_DIR = RESULTS_DIR / "variable_labels"
RUNS_DIR = RESULTS_DIR / "runs"
LOGS_DIR = RESULTS_DIR / "logs"

METHOD_REVIEW_FIELDNAMES = [
    "sample_key",
    "case_id",
    "suggested_method",
    "proposed_new_category",
    "reason",
]

VARIABLE_REVIEW_FIELDNAMES = [
    "sample_key",
    "round",
    "is_accurate",
    "missing_variables",
    "redundant_variables",
    "incorrect_fields",
    "reason",
    "revision_advice",
]

VARIABLE_FINAL_REVIEW_FIELDNAMES = ["sample_key", "modify", "reason"]

ALLOWED_VARIABLE_CLASSES = {"numerical", "categorical", "others"}
ALLOWED_VARIABLE_ROLES = {"X", "Y", "XY", "NR"}

VARIABLE_CLASS_ALIASES = {
    "numeric": "numerical",
    "number": "numerical",
    "continuous": "numerical",
    "discrete": "categorical",
    "category": "categorical",
    "nominal": "categorical",
    "boolean": "categorical",
    "bool": "categorical",
}

VARIABLE_ROLE_ALIASES = {
    "independent": "X",
    "dependent": "Y",
    "both": "XY",
    "nr": "NR",
    "none": "NR",
    "na": "NR",
    "n/a": "NR",
    "not applicable": "NR",
    "not relevant": "NR",
    "parameter": "NR",
    "identifier": "NR",
    "index": "NR",
    "grouping": "NR",
}


def ensure_results_tree() -> None:
    for path in (
        METHOD_REVIEW_DIR,
        VARIABLE_LABELS_DIR,
        RUNS_DIR,
        LOGS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def results_dir_name_for_model(model_name: str, default_model: str = "gpt-4o") -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", model_name).strip("._-")
    if not safe_name:
        safe_name = "custom_model"
    return f"results/{safe_name}"


def set_results_root_for_model(model_name: str, default_model: str = "gpt-4o") -> Path:
    global RESULTS_DIR, METHOD_REVIEW_DIR, VARIABLE_LABELS_DIR, RUNS_DIR, LOGS_DIR

    RESULTS_DIR = PROJECT_ROOT / "label_construct" / results_dir_name_for_model(model_name, default_model)
    METHOD_REVIEW_DIR = RESULTS_DIR / "method_review"
    VARIABLE_LABELS_DIR = RESULTS_DIR / "variable_labels"
    RUNS_DIR = RESULTS_DIR / "runs"
    LOGS_DIR = RESULTS_DIR / "logs"
    ensure_results_tree()
    return RESULTS_DIR


def resolve_results_dir_for_model(model_name: str, default_model: str = "gpt-4o") -> Path:
    return PROJECT_ROOT / "label_construct" / results_dir_name_for_model(model_name, default_model)


def get_results_dir() -> Path:
    return RESULTS_DIR


def get_method_review_dir() -> Path:
    return METHOD_REVIEW_DIR


def get_runs_dir() -> Path:
    return RUNS_DIR


def get_logs_dir() -> Path:
    return LOGS_DIR


def build_logger(name: str) -> logging.Logger:
    ensure_results_tree()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(LOGS_DIR / f"{name}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def sample_sort_key(path: Path) -> tuple[int, str]:
    try:
        return int(path.stem), path.name
    except ValueError:
        return 10**9, path.name


def iter_sample_paths(sample_dir: Path | None = None, limit: int | None = None) -> list[Path]:
    directory = sample_dir or INPUT_DIR
    paths = sorted(directory.glob("*.json"), key=sample_sort_key)
    if limit is not None:
      k = max(0, min(limit, len(paths)))
      random.seed(100)
      paths = random.sample(paths, k=k)
    return paths


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        repaired = repair_json_like_text(content)
        if repaired != content:
            return json.loads(repaired)
        raise


def repair_json_like_text(text: str) -> str:
    if not text:
        return text

    repaired = text.strip()
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

    chars: list[str] = []
    in_string = False
    expecting_key = False
    stack: list[str] = []
    index = 0

    def next_non_space(cursor: int) -> str:
        cursor += 1
        while cursor < len(repaired) and repaired[cursor].isspace():
            cursor += 1
        if cursor >= len(repaired):
            return ""
        return repaired[cursor]

    while index < len(repaired):
        char = repaired[index]

        if not in_string:
            chars.append(char)
            if char == "{":
                stack.append("{")
                expecting_key = True
            elif char == "[":
                stack.append("[")
                expecting_key = False
            elif char == "}":
                if stack:
                    stack.pop()
                expecting_key = False
            elif char == "]":
                if stack:
                    stack.pop()
                expecting_key = False
            elif char == ",":
                expecting_key = bool(stack and stack[-1] == "{")
            elif char == ":":
                expecting_key = False
            elif char == "\"":
                in_string = True
            index += 1
            continue

        if char == "\\":
            next_char = repaired[index + 1] if index + 1 < len(repaired) else ""
            if next_char in {"\"", "\\", "/"}:
                chars.append(char)
                chars.append(next_char)
                index += 2
                continue
            if next_char == "u" and index + 5 < len(repaired):
                hex_part = repaired[index + 2 : index + 6]
                if re.fullmatch(r"[0-9a-fA-F]{4}", hex_part):
                    chars.append(char)
                    chars.append("u")
                    chars.extend(hex_part)
                    index += 6
                    continue
            chars.append("\\\\")
            index += 1
            continue

        if char == "\"":
            following = next_non_space(index)
            is_closing_quote = following in {",", "}", "]", ":", ""}
            if is_closing_quote:
                chars.append(char)
                in_string = False
                if expecting_key and following == ":":
                    expecting_key = False
            else:
                chars.append("\\\"")
            index += 1
            continue

        if char == "\n":
            chars.append("\\n")
            index += 1
            continue

        if char == "\r":
            chars.append("\\r")
            index += 1
            continue

        if char == "\t":
            chars.append("\\t")
            index += 1
            continue

        chars.append(char)
        index += 1

    return "".join(chars)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _serialize_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_rows = []
    for row in rows:
        normalized_rows.append({field: _serialize_csv_value(row.get(field, "")) for field in fieldnames})

    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(normalized_rows)


def load_existing_rows_by_key(path: Path, key_field: str = "sample_key") -> dict[str, dict[str, str]]:
    rows = load_csv_rows(path)
    return {row[key_field]: row for row in rows if row.get(key_field)}


def normalize_flag(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return 1 if value else 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return 1
    if text in {"0", "false", "no", "n", ""}:
        return 0
    raise ValueError(f"无法识别的布尔标记: {value}")


def get_variable_round_dir(round_index: int) -> Path:
    return VARIABLE_LABELS_DIR / f"round_{round_index}"


def get_variable_round_samples_dir(round_index: int) -> Path:
    return get_variable_round_dir(round_index) / "samples"


def get_variable_label_path(sample_key: str, round_index: int) -> Path:
    return get_variable_round_samples_dir(round_index) / f"{sample_key}.json"


def get_variable_label_path_for_model(
    model_name: str,
    sample_key: str,
    round_index: int,
    default_model: str = "gpt-4o",
) -> Path:
    return (
        resolve_results_dir_for_model(model_name, default_model)
        / "variable_labels"
        / f"round_{round_index}"
        / "samples"
        / f"{sample_key}.json"
    )


def get_variable_review_path(round_index: int) -> Path:
    return get_variable_round_dir(round_index) / "review.csv"


def get_final_dir() -> Path:
    return VARIABLE_LABELS_DIR / "final"


def get_final_samples_dir() -> Path:
    return get_final_dir() / "samples"


def get_final_review_path() -> Path:
    return get_final_dir() / "review.csv"


def get_final_samples_dir_for_model(model_name: str, default_model: str = "gpt-4o") -> Path:
    return resolve_results_dir_for_model(model_name, default_model) / "variable_labels" / "final" / "samples"


def get_final_review_path_for_model(model_name: str, default_model: str = "gpt-4o") -> Path:
    return resolve_results_dir_for_model(model_name, default_model) / "variable_labels" / "final" / "review.csv"


def to_project_relative(path: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = PROJECT_ROOT.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def build_variable_label_record(sample: dict[str, Any], source_path: Path, round_index: int, variables: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_key": str(sample.get("sample_key", "")),
        "case_id": sample.get("case_id", ""),
        "source_path": to_project_relative(source_path),
        "round": round_index,
        "variables": variables,
    }


def normalize_variable_class(value: Any) -> str:
    text = str(value).strip()
    lowered = text.lower()
    normalized = VARIABLE_CLASS_ALIASES.get(lowered, text)
    if normalized not in ALLOWED_VARIABLE_CLASSES:
        raise ValueError(f"class 不合法: {value}")
    return normalized


def normalize_variable_role(value: Any) -> str:
    text = str(value).strip()
    upper_text = text.upper()
    if upper_text in ALLOWED_VARIABLE_ROLES:
        return upper_text

    lowered = text.lower()
    normalized = VARIABLE_ROLE_ALIASES.get(lowered, text)
    if normalized not in ALLOWED_VARIABLE_ROLES:
        raise ValueError(f"role 不合法: {value}")
    return normalized


def validate_variable_payload(variables: Any) -> dict[str, Any]:
    if not isinstance(variables, dict):
        raise ValueError("变量输出必须是JSON对象")

    for key, payload in variables.items():
        if not isinstance(payload, dict):
            raise ValueError(f"变量 {key} 的值必须是JSON对象")

        for required in ("id", "value", "class", "role", "description"):
            if required not in payload:
                raise ValueError(f"变量 {key} 缺少字段 {required}")

        if str(payload["id"]) != str(key):
            raise ValueError(f"变量键 {key} 与 id 字段 {payload['id']} 不一致")

        try:
            payload["class"] = normalize_variable_class(payload["class"])
        except ValueError as exc:
            raise ValueError(f"变量 {key} 的 {exc}") from exc

        try:
            payload["role"] = normalize_variable_role(payload["role"])
        except ValueError as exc:
            raise ValueError(f"变量 {key} 的 {exc}") from exc

        if not isinstance(payload["description"], str) or not payload["description"].strip():
            raise ValueError(f"变量 {key} 的 description 不能为空")

    return variables


def get_selected_sample_map(sample_paths: list[Path]) -> dict[str, Path]:
    return {path.stem: path for path in sample_paths}


def parse_json_cell(value: str) -> Any:
    value = (value or "").strip()
    if not value:
        return []
    return json.loads(value)


def copy_json_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def latest_existing_label_path(sample_key: str, max_rounds: int) -> Path | None:
    for round_index in range(max_rounds, -1, -1):
        candidate = get_variable_label_path(sample_key, round_index)
        if candidate.exists():
            return candidate
    return None


def latest_review_round(sample_key: str, max_rounds: int) -> int | None:
    for round_index in range(max_rounds, -1, -1):
        review_path = get_variable_review_path(round_index)
        if not review_path.exists():
            continue
        for row in load_csv_rows(review_path):
            if row.get("sample_key") == sample_key:
                return round_index
    return None
