#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import Any

from prompt import prompt_gen_0


METHOD_TAXONOMY_START = '"method"字段的内容须严格来自以下框架（结果应来自[]中的内容）'
METHOD_TAXONOMY_END = '注意："background"，"query"，"answer"字段仍用英文表述。"method"字段用中文表述。'
METHOD_TAXONOMY_TEXT = prompt_gen_0.split(METHOD_TAXONOMY_START, 1)[1].split(METHOD_TAXONOMY_END, 1)[0].strip()
VARIABLE_REQUIREMENTS_TEXT = '''
关键要求：
1. 以 `answer` 的实际推理和计算过程为最高优先级；题面中出现但 answer 未实际使用的变量不要保留。
2. 变量对象可以是原始数据列、分组统计量、列联表、样本量、成功次数、时间变量，或任何被 answer 明确调用的数据对象。请注意，当 answer 中利用了题目中的多个变量构造了一个新的变量时，应当只保留并且全部保留这些原始变量，而不需要单独构造一个新的变量对象。
3. 若 answer 只使用了数据中的部分列，只输出这些列。
4. 若 answer 没有实际使用任何变量对象，输出空 JSON：{{}}。
5. 输出必须是严格 JSON，顶层以变量 id 为 key，不要输出额外文字。
6. 变量特指question中为了研究目标问题所采集的数据对象及其统计量（如样本量、均值、标准差等），不包括模型参数、与特定统计模型/分布相关的统计量（例如z score、p值）以及与特定统计方法相关的统计量（例如t值、F值）。

字段规范：
- 顶端key: "变量名（提取自题目或自行指定合适的变量名）"。
- `id`: 变量标识，必须与顶层 key 完全一致。
- `value`: 当前变量的完整取值。若为表格中的一列，可用数组；若为汇总量（包括统计量、sample size等），可用 JSON 值（key为汇总量名称，value为对应取值）；若以上两种形式均难以表示，则复制粘贴题面中该变量的原始记录形式（如 tex 语法记录的表格）。当value中有多个数值时，请确保它们的顺序与题目中的原始顺序一致。
- `class`: 只能取 `numerical`、`categorical`、`others` 之一。(（数值型记为"numerical",分类型记为"categorical"，不属于上述类别的记为"others"）
- `role`: 只能取 `X`、`Y`、`XY`、`NR` 之一。
  - `X`: 自变量。是指由研究者主动操纵或自然存在的、不受其他变量影响的变量。它是引起其他变量变化的原因或条件。此处用于构造自变量的原始变量也属于该角色。
  - `Y`: 因变量或被解释变量。是指由于自变量的变化而被引起变化的变量。它是研究者观察和测量的结果。此处用于构造因变量的原始变量也属于该角色。
  > 请注意，只有当变量之间关系存在明确方向性时，才区分 `X` 和 `Y`（两者总是相伴出现的）。
  - `XY`: 是指研究两个（多个）变量之间的相关性但没有区分因果的必要，或该变量兼具因果两种角色。
  - `NR`: 不必指定方向。是指在分析中不必区分因变量和自变量。一般包括以下几种情况：
      - 仅作为样本标识或索引的变量，因需要匹配多个数据集的样本而必须纳入相关变量（variable）集合的。
      - 仅作用于筛选部分样本进行分析（如研究2020年的数据时的“年份”变量）的变量而必须纳入相关变量（variable）集合的。
      - 无监督方法（聚类、降维）涉及的相关变量。
      - 仅用于描述变量的数值分布情况，或时间序列的平稳性时涉及的相关变量。
> `role`的特殊情况：
    1. 对于“数据可视化“中的“时间变化趋势”类问题，需要将表示时间概念的变量作为independent，随时间变化的变量作为dependent（即使变量集合中未出现时间变量）。例如，研究不同时间点的销售量变化趋势，时间变量作为independent，销售量变量作为dependent。
    2. 如果一个变量既作为自变量又用于构造因变量，该变量的角色为自变量。
    3. 如果一个变量既作为因变量又用于构造自变量，该变量的角色为因变量。
- `description`: 对变量对象的简要描述。
'''


def _pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_method_review_prompt(sample: dict[str, Any]) -> str:
    payload = {
        "background": sample.get("input", {}).get("background", ""),
        "data": sample.get("input", {}).get("data", ""),
        "question": sample.get("input", {}).get("question", ""),
        "answer": sample.get("output", {}).get("answer", ""),
        "current_method": sample.get("output", {}).get("method", ""),
    }
    return f"""
你是一个严格的统计学教材标注审稿人。你需要判断给定样本中的 `answer` 与现有 `method` 是否一致。具体而言，“不一致“指的是，现有 method taxonomy 中，有比现有 `method` 更适合概括当前样本的二级类别，或者你认为现有 taxonomy 中的二级类别都不适合当前样本，需要新增类别。

评审要求：
1. `method` 的分类结果应当主要根据给定样本需要解决的是什么类型的问题来判断。`answer` 的实际求解过程、使用的统计方法和计算目标可以作为重要参考。
2. 若现有 `method` 一致，则保持该标签。
3. 若不一致，但能映射到现有 taxonomy 中的其它类别，则给出 `suggested_method`。
4. 若现有 taxonomy 的类别都不合适，可将 `needs_new_category` 置为 1，并给出 `proposed_new_category`。`proposed_new_category`应当优先考虑在现有 taxonomy 框架下新增二级类别，然后再考虑新增一级类别。
5. 理由必须具体，指出是“应改到现有哪个类别”还是“为什么需要新增类别”。
6. 输出必须是严格 JSON，不要输出额外说明。

现有 method taxonomy 如下：
{METHOD_TAXONOMY_TEXT}

样本：
{_pretty_json(payload)}

请输出：
{{
  "is_consistent": 1,
  "current_method": "当前方法标签",
  "suggested_method": "若一致则与 current_method 相同；若不一致则填建议类别；若建议新增且无法映射则填空字符串",
  "needs_new_category": 0,
  "proposed_new_category": "若无需新增则填空字符串",
  "reason": "具体理由"
}}
""".strip()


def build_variable_extract_prompt(sample: dict[str, Any]) -> str:
    payload = {
        "background": sample.get("input", {}).get("background", ""),
        "data": sample.get("input", {}).get("data", ""),
        "question": sample.get("input", {}).get("question", ""),
        "answer": sample.get("output", {}).get("answer", ""),
    }
    return f"""
你是一个严格的统计学教材标注员。请根据题目输入和参考答案，提取“answer 在实际求解中真正使用到的变量对象”。

要求：
{VARIABLE_REQUIREMENTS_TEXT}

样本：
{_pretty_json(payload)}

输出示例：
{{
  "VAR_NAME": {{
    "id": "VAR_NAME",
    "value": [1, 2, 3],
    "class": "numerical",
    "role": "Y",
    "description": "Outcome variable used in the answer."
  }}
}}
""".strip()


def build_variable_review_prompt(sample: dict[str, Any], variable_record: dict[str, Any], review_round: int) -> str:
    payload = {
        "review_round": review_round,
        "background": sample.get("input", {}).get("background", ""),
        "data": sample.get("input", {}).get("data", ""),
        "question": sample.get("input", {}).get("question", ""),
        "answer": sample.get("output", {}).get("answer", ""),
        "variables": variable_record.get("variables", {}),
    }
    return f"""
你是一个严格的统计学变量标注审稿人。请检查给定变量抽取结果是否满足以下要求：
{VARIABLE_REQUIREMENTS_TEXT}

请只围绕以下四类问题审稿：
1. 是否遗漏了 answer 实际使用到的变量对象。
2. 是否抽取了 answer 未实际使用的冗余变量。
3. 每个变量的 `class`、`role`、`description` 是否正确。
4. `value` 是否与题面数据一致，或是否存在结构问题。

输出必须是严格 JSON，不要输出额外说明。格式如下：
{{
  "is_accurate": 1,
  "missing_variables": [],
  "redundant_variables": [],
  "incorrect_fields": [
    {{
      "id": "变量id",
      "field": "class/role/value/description",
      "issue": "问题描述",
      "suggestion": "修改建议"
    }}
  ],
  "reason": "总体判断理由",
  "revision_advice": "若不准确，给出可直接执行的修正建议；若准确则填 无"
}}

样本：
{_pretty_json(payload)}
""".strip()


def build_variable_refine_prompt(
    sample: dict[str, Any],
    previous_variable_record: dict[str, Any],
    review_row: dict[str, Any],
    refine_round: int,
) -> str:
    payload = {
        "refine_round": refine_round,
        "background": sample.get("input", {}).get("background", ""),
        "data": sample.get("input", {}).get("data", ""),
        "question": sample.get("input", {}).get("question", ""),
        "answer": sample.get("output", {}).get("answer", ""),
        "previous_variables": previous_variable_record.get("variables", {}),
        "review_feedback": {
            "missing_variables": review_row.get("missing_variables", []),
            "redundant_variables": review_row.get("redundant_variables", []),
            "incorrect_fields": review_row.get("incorrect_fields", []),
            "reason": review_row.get("reason", ""),
            "revision_advice": review_row.get("revision_advice", ""),
        },
    }
    return f"""
你是一个负责修正统计学变量标签的标注员。请根据题目、参考答案、上一轮变量结果和审稿意见，产出修正版变量标签。

变量标签的要求和字段规范请参考以下内容：
{VARIABLE_REQUIREMENTS_TEXT}

修正要求：
1. 只保留 answer 实际使用到的变量对象。
2. 必须解决审稿意见指出的问题。
3. 顶层输出必须仍然是以变量 id 为 key 的严格 JSON。
4. 每个变量对象必须包含 `id`、`value`、`class`、`role`、`description`。
5. `class` 只能取 `numerical`、`categorical`、`ordinal`、`binary`。
6. `role` 只能取 `X`、`Y`、`XY`、`NR`。
7. 不要输出额外说明文字。

输入：
{_pretty_json(payload)}
""".strip()
