# 统计学习题处理

## 结构

```
bookassign/
├── label_construct/    # 标签构建与审阅流水线_v2
├── book1/              # 原始JSON文件目录
├── book1_r1/           # 处理后的JSON文件目录
├── book1_r2/           # 分割后的JSON文件目录
├── api_info.py         # API配置文件
├── prompt.py           # 提示词文件
├── process_book1.py    # 核心处理脚本
├── process_variables.py # 提取变量的脚本
├── judge_exercises.py  # 判断习题是否符合要求的脚本
├── split_json.py       # 分割JSON文件的脚本
└── README.md           # 项目说明文件
```

`label_construct/` 下的新流程会把“代码”和“结果”分离管理，不再回写 `book1_r2/*.json`。运行后生成的结果默认落在 `label_construct/results/`。

## 环境要求

- Python 3.7+
- OpenAI SDK
- 其他依赖库（会自动安装）

## 配置说明

1. **API配置**：在 `api_info.py` 文件中配置OpenAI API密钥和基础URL
   ```python
   api_key = "your_api_key"
   base_url = "https://api.openai.com/v1"  # 或其他兼容的API端点
   ```

2. **提示词配置**：在 `prompt.py` 文件中定义了三个提示词：
   - `prompt_gen_0`：用于习题格式转换
   - `prompt_gen_1`：用于提取变量信息
   - `prompt_check_0`：用于判断习题是否符合要求

## 使用方法

### 1. 分割JSON文件

将原始JSON文件分割为单个习题文件：

```bash
python split_json.py
```

### 2. 处理习题并提取变量

处理所有习题并提取变量信息：

```bash
python process_variables.py
```

### 3. 判断习题是否符合要求

判断习题是否适合检测学生的统计学水平，并生成CSV结果：

```bash
python judge_exercises.py
```

### 4. 核心处理（完整流程）

执行完整的处理流程，包括格式转换、变量提取等：

```bash
python process_book1.py
```

### 5. 标签构建与审阅流水线_v2

当前版本的标签流水线代码位于 `label_construct/`，默认针对类似 `book1_r3`、`book2_r3` 这样的样本目录运行，并把结果统一写入 `label_construct/results_final/<目录名>/`。方法标签与变量标签不再回写到原始样本 JSON。

#### 5.1 完整运行

对单个目录运行方法审阅、变量抽取、变量终审：

```bash
python3 label_construct/run_pipeline.py \
  --input-dirs book1_r3 \
  --model_major claude-opus-4-6 \
  --model_suggest gpt-5.4
```

对多个目录串行运行：

```bash
python3 label_construct/run_pipeline.py \
  --input-dirs book1_r3 book2_r3 book3_r3 \
  --model_major claude-opus-4-6 \
  --model_suggest gpt-5.4
```

如果只想运行前两个阶段：

```bash
python3 label_construct/run_pipeline.py \
  --input-dirs book1_r3 \
  --model_major claude-opus-4-6 \
  --stages method_review,variable_extract
```

#### 5.2 方法审阅的单独运行与缓存预处理

只对某个目录做方法审阅：

```bash
python3 label_construct/method_review.py \
  --input-dir book1_r3 \
  --model claude-opus-4-6
```

只做 `method_review.csv` 的缓存预处理（将二级标题转化为“一级\二级”格式），不调用 LLM：

```bash
python3 label_construct/method_review.py \
  --input-dir book1_r3 \
  --normalize-cache-only
```

#### 5.3 常用参数

- `--input-dirs ...`：`run_pipeline.py` 的输入目录列表，支持一个或多个样本目录。
- `--input-dir ...`：`method_review.py` 的单目录入口。
- `--model_major`：主模型，用于方法审阅、主变量抽取和变量终审。
- `--model_suggest`：建议模型；提供后会额外生成一份 suggest 变量抽取结果，并进入 `variable_finalize`。
- `--stages ...`：可选 `method_review`、`variable_extract`、`variable_finalize`。
- `--limit N`：只处理当前目录中的前 `N` 条样本，适合调试。
- `--force`：忽略已有缓存，强制重跑。
- `--max-workers N`：控制并发请求数。
- `--update_method true/false`：控制方法审阅的缓存命中规则。
  - `true`：要求 `method_review.csv` 中 `suggested_method` 非空，且为 `一级类目名\二级类目名` 格式。
  - `false`：只要 `sample_key` 已存在于 `method_review.csv` 就算命中缓存。

#### 5.4 标签结果的保存方式、格式与路径

当前版本有两类标签结果：方法标签与变量标签。它们都保存在 `label_construct/results_final/<目录名>/` 下。

1. 方法标签

- 路径：`label_construct/results_final/<目录名>/method_review/method_review.csv`
- 格式：CSV
- 字段：
  - `sample_key`
  - `case_id`
  - `suggested_method`
  - `proposed_new_category`
  - `reason`
- 说明：
  - `suggested_method` 现要求为 `一级类目名\二级类目名`
  - 若现有 taxonomy 不合适，则 `suggested_method` 为空，`proposed_new_category` 填建议新增类目

2. 变量标签

- 主路径：
  - `label_construct/results_final/<目录名>/variable_labels/round_0/samples/*.json`
  - `label_construct/results_final/<目录名>/variable_labels/final/samples/*.json`
  - `label_construct/results_final/<目录名>/variable_labels/final/review.csv`
- 格式：
  - 样本级标签为 JSON
  - 终审记录为 CSV
- JSON 结构（样本级）：
  - 顶层包含 `sample_key`、`case_id`、`source_path`、`round`、`variables`
  - `variables` 是一个以变量 id 为 key 的对象，每个变量包含：
    - `id`
    - `value`
    - `class`
    - `role`
    - `description`
- `final/review.csv` 字段：
  - `sample_key`
  - `modify`
  - `reason`

3. 运行日志与摘要

- 日志路径：`label_construct/results_final/<目录名>/logs/*.log`
- 流水线摘要：`label_construct/results_final/<目录名>/runs/summary.json`
- 当提供 `model_suggest` 时，suggest 模型的中间变量抽取结果也会写在该目录下的私有子目录中，不与其他教材目录混用

## 输出说明

1. **分割后的文件**：保存在 `book1_r2` 目录中，每个文件对应一个习题

2. **变量提取结果**：直接更新到 `book1_r2` 目录中的JSON文件，添加 `output.variable` 字段

3. **判断结果**：生成 `exercise_judgments.csv` 文件，包含以下列：
   - `sample_key`：原问题的样本键
   - `case_id`：原问题的案例ID
   - `background`：原问题的背景
   - `data`：原问题的数据
   - `question`：原问题的问题
   - `judge`：判断结果（1代表适合，0代表不适合）
   - `explanation`：判断理由

4. **处理报告**：生成各种处理报告，如 `variables_processing_report.txt` 和 `exercise_judgment_report.txt`

5. **标签流水线 v2 结果**：默认保存在 `label_construct/results_final/<目录名>/`，主要包括：
   - `method_review/method_review.csv`
   - `variable_labels/round_0/samples/*.json`
   - `variable_labels/final/samples/*.json`
   - `variable_labels/final/review.csv`
   - `runs/summary.json`
   - `logs/*.log`


## 示例输出

### 变量提取示例

```json
{
  "sample_key": "1",
  "case_id": "1",
  "input": {
    "background": "The table below shows the cigarette consumption per capita (CIG1930) and lung cancer mortality per 100,000 people (LUNGCA) for 11 countries in 1930 and 1950, respectively.",
    "data": "\\begin{tabular}{ccc} \\\nCountry & CIG1930 & LUNGCA \\\\ \\\n\\hline \\\nAustralia & 480 & 18.3 \\\\ \\\nCanada & 500 & 15.9 \\\\ \\\nDenmark & 380 & 18.1 \\\\ \\\nFinland & 1100 & 22.1 \\\\ \\\nGreat Britain & 1100 & 29.8 \\\\ \\\nIceland & 230 & 5.3 \\\\ \\\nNetherlands & 490 & 15.3 \\\\ \\\nNorway & 250 & 9.2 \\\\ \\\nSweden & 300 & 11.1 \\\\ \\\nSwitzerland & 510 & 25.3 \\\\ \\\nUnited States & 1300 & 26.6 \\\\ \\\n\\end{tabular}",
    "question": "What is the value of the LUNGCA variable for the seventh observation?"
  },
  "output": {
    "variable": {
      "COUNTRY": {
        "id": "COUNTRY",
        "value": ["Australia", "Canada", "Denmark", "Finland", "Great Britain", "Iceland", "Netherlands", "Norway", "Sweden", "Switzerland", "United States"],
        "class": "categorical",
        "role": "NR",
        "description": "Country name"
      },
      "CIG1930": {
        "id": "CIG1930",
        "value": [480, 500, 380, 1100, 1100, 230, 490, 250, 300, 510, 1300],
        "class": "numerical",
        "role": "independent",
        "description": "Cigarette consumption per capita in 1930"
      },
      "LUNGCA": {
        "id": "LUNGCA",
        "value": [18.3, 15.9, 18.1, 22.1, 29.8, 5.3, 15.3, 9.2, 11.1, 25.3, 26.6],
        "class": "numerical",
        "role": "dependent",
        "description": "Lung cancer mortality per 100,000 people"
      }
    }
  }
}
```

### 判断结果示例

| sample_key | case_id | background | data | question | judge | explanation |
|------------|---------|------------|------|----------|-------|-------------|
| 1 | 1 | The table below shows... | \begin{tabular}{ccc}... | What is the value of the LUNGCA variable for the seventh observation? | 0 | 该问题仅要求识别某个数据，属于过于基础或简单的问题。 |


。
