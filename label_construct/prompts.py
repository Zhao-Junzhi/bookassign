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
2.1 如果题目没有给出显式数据表或 `data` 为空，但 `question` / `answer` 中已经出现了符号变量、统计量或逻辑判断对象（如 `X`、`Y`、`r`、某个事件、某个统计量），仍然需要据此抽取变量；这不属于“缺少输入”。
3. 若 answer 只使用了数据中的部分列，只输出这些列。
4. 若 answer 没有实际使用任何变量对象，输出空 JSON：{{}}。
5. 样本已经完整提供。无论 `background`、`data` 是否为空，都禁止回复“请提供题目/答案/输入/上下文”等索要补充信息的话；若信息不足以支持任何变量，直接输出空 JSON：{{}}。
6. 输出必须是严格 JSON，顶层以变量 id 为 key，不要输出额外文字。
7. 变量特指question中为了研究目标问题所采集的数据对象及其统计量（如样本量、均值、标准差等），不包括模型参数、与特定统计模型/分布相关的统计量（例如z score、p值）以及与特定统计方法相关的统计量（例如t值、F值）。

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
    }
    return f"""
你是一个严格的统计学教材方法标签标注员。请根据给定样本的 `background`、`data`、`question` 和现有 `method taxonomy`，为当前问题选择最合适的 `method` 二级类目。

要求：
1. 如果现有 taxonomy 中，存在明确的，非常适合于描述当前问题的二级类目，请选择最贴切的，并将其写入 `suggested_method`。
2. 如果现有 taxonomy 中所有二级类目都不是特别合适，则填写 `proposed_new_category`。当拿不准时，请倾向于建议新增，以便后续完善 taxonomy。
3. 一旦填写 `proposed_new_category`，`suggested_method` 必须为空字符串。
4. `reason` 必须具体说明为何该问题属于某个现有二级类目，或为何必须新增类目。
5. 输出必须是严格 JSON，不要输出额外说明。

现有 method taxonomy 如下：
{METHOD_TAXONOMY_TEXT}

样本：
{_pretty_json(payload)}

请输出：
{{
  "suggested_method": "taxonomy 中最合适的二级类目；若建议新增则填空字符串",
  "proposed_new_category": "若 taxonomy 中都不合适则填写建议新增类目，否则填空字符串",
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


def build_variable_extract_retry_prompt(sample: dict[str, Any]) -> str:
    return (
        build_variable_extract_prompt(sample)
        + "\n\n补充要求：你已经拿到了完整样本。"
        + " 不允许回答“Please provide ...”或“请提供 ...”。"
        + " 若 `data` 为空，请直接根据 `question` 和 `answer` 中出现的符号、统计量或判断对象抽取变量；"
        + " 若确实不存在应抽取的变量，只返回 {}。"
    )


def build_variable_finalize_prompt(
    sample: dict[str, Any],
    major_model: str,
    major_variable_record: dict[str, Any],
    suggest_model: str,
    suggest_variable_record: dict[str, Any],
) -> str:
    payload = {
        "background": sample.get("input", {}).get("background", ""),
        "data": sample.get("input", {}).get("data", ""),
        "question": sample.get("input", {}).get("question", ""),
        "answer": sample.get("output", {}).get("answer", ""),
        "major_model": major_model,
        "major_variables": major_variable_record.get("variables", {}),
        "suggest_model": suggest_model,
        "suggest_variables": suggest_variable_record.get("variables", {}),
    }
    return f"""
你是一个严格的统计学变量标签终审员。现在需要你复核两个模型的变量抽取结果，但应当以 `major_model` 的结果为主导。

变量标签的要求和字段规范请参考以下内容：
{VARIABLE_REQUIREMENTS_TEXT}

请只围绕以下四类问题审稿：
1. 是否遗漏了 answer 实际使用到的变量对象。
2. 是否抽取了 answer 未实际使用的冗余变量。
3. 每个变量的 `class`、`role`、`description` 是否正确。
4. `value` 是否与题面数据一致，或是否存在结构问题。

终审要求：
1. 以 `major_model` 的变量结果为主要依据。
2. `suggest_model` 的能力弱于 `major_model`，其结果仅供参考，不能默认采纳。
3. 如果你判断 `suggest_model` 的部分结果更合理，可以据此调整 `major_model` 的结果；但不要机械照抄，因为两个模型都可能有误。
4. 若无需调整，返回 `modify = 0`，并将 `revised_variables` 置为空 JSON：{{}}。
5. 若需要调整，返回 `modify = 1`，并在 `revised_variables` 中给出修订后的完整变量 JSON。
6. `reason` 需要明确说明为何保持原结果，或为何调整以及调整依据。
7. 输出必须是严格 JSON，不要输出额外说明。

输入：
{_pretty_json(payload)}

请输出：
{{
  "modify": 0,
  "reason": "具体理由",
  "revised_variables": {{}}
}}
""".strip()
