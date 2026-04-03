# 统计学习题处理

## 结构

```
bookassign/
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
