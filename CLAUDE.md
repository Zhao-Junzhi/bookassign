# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project automates processing of statistics textbook exercises (统计学教材习题) to create structured datasets suitable for evaluating LLM statistical reasoning abilities.

## Running the Pipeline

All scripts use an OpenAI-compatible API. Configure credentials before running:

```python
# api_info.py
api_key = "your_api_key"
base_url = "https://..."  # OpenAI-compatible endpoint
```

**Pipeline steps (run in order):**

```bash
# Step 1: Reformat raw exercises into structured JSON (book1/ → book1_r1/)
python process_book1.py

# Step 2: Flatten multi-part questions into individual samples (book1_r1/ → data0_book1.json/.pkl)
python get_data.py

# Step 3: Split aggregated JSON into per-sample files (data0_book1.json → book1_r2/)
python split_json.py

# Step 4: Extract statistical variables for each sample (adds output.variable to book1_r2/*.json)
python process_variables.py

# Step 5: Judge whether exercises are suitable for testing statistical ability (→ exercise_judgments.csv)
python judge_exercises.py
```

Each script skips already-processed files, so re-runs are safe.

## Architecture

### Data Flow

```
book1/*.json          (292 raw records, non-strict JSON)
    ↓ process_book1.py + prompt_gen_0
book1_r1/*.json       (277 records: background + task[] with query/answer/method)
    ↓ get_data.py
data0_book1.json/.pkl (588 flat samples keyed 1..588)
    ↓ split_json.py
book1_r2/*.json       (586 per-sample files, missing 14 and 224)
    ↓ process_variables.py + prompt_gen_1
book1_r2/*.json       (output.variable added to 573/586)
    ↓ judge_exercises.py + prompt_check_0
exercise_judgments.csv (586 rows: judge=1 → 346, judge=0 → 240)
```

### Key Files

- **`api_info.py`** — API key and base URL (not committed with real credentials)
- **`prompt.py`** — Three prompts:
  - `prompt_gen_0`: Reformats question+answer into `{background, task[{query, answer, method}]}`; `method` must match a fixed taxonomy of ~50 Chinese statistical method labels
  - `prompt_gen_1`: Extracts variables (id, value, class, role, description) from background/data/question
  - `prompt_check_0`: Judges exercise quality (1=suitable, 0=too simple/unclear)
- **`process_book1.py`** — Uses regex-based `read_json_file()` instead of `json.load()` because raw files have escape errors and BOM markers; async with semaphore for rate limiting
- **`parse_json_regex.py`** — Standalone regex JSON parser

### Sample JSON Schema (book1_r2/)

```json
{
  "sample_key": "42",
  "case_id": "book1_r1/record_XXX.json",
  "input": { "background": "...", "data": "LaTeX table...", "question": "..." },
  "output": {
    "answer": "...",
    "method": "统计方法类别",
    "variable": { "VAR_NAME": { "id", "value", "class", "role", "description" } }
  },
  "meta_info": { "chapter": "...", "section": "...", "page": "..." }
}
```

## Known Issues

- **Windows paths** hardcoded in scripts (e.g., `d:\place\study\bookassign\...`). Change `INPUT_DIR`/`OUTPUT_DIR` at the top of each script before running on macOS/Linux.
- **Missing samples**: `book1_r2/14.json` and `book1_r2/224.json` do not exist and are absent from `exercise_judgments.csv`.
- **Missing variables**: 13 samples lack `output.variable`; 6 of these have `judge=1` (IDs: 34, 187, 276, 347, 353, 354).
- **LLM JSON parsing**: Model outputs sometimes contain comments (`// ...`), ellipses, or natural language — `parse_model_output()` handles markdown code blocks, bare JSON, and brace-extracted fallback.
