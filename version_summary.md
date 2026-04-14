# v0已完成工作梳理

截至时间：2026-04-04

## 1. 仓库内容与目标理解

该项目围绕“统计学教材习题”数据做自动化处理，目标是把教材中提取的问答对/习题转换成更适合大模型评测的数据结构，并进一步：
> 默认询问的模型是 gpt4o

- 对习题做一轮筛选，剔除过于基础或难以理解的问题，保留更能检验统计能力的题目。
- 对保留题目抽取“解题所需变量信息”（变量名、取值、类型、角色、描述）。
- 在重编排阶段给每个子问题附带一个“统计方法类别”标签（`output.method`），供后续使用或再加工。

## 2. 目录与关键文件

- `book1/`：原始题目文件（292 个 `record_*.json`，部分文件并非严格 JSON）。
- `book1_r1/`：经 LLM 重编排后的题目文件（277 个 `record_*.json`）。
> 重编排具体做了什么？
- `data0_book1.json` / `data0_book1.pkl`：将 `book1_r1` 中的多子问题“扁平化”为单条样本后的聚合数据（588 条）。
> `data0_book1.json` / `data0_book1.pkl` 内容是否完全一致？
- `book1_r2/`：按条拆分后的单样本 JSON（当前 586 个文件；理论应为 588，缺失 `14.json`、`224.json`）。
> 缺失的原因？
- `exercise_judgments.csv`：对 `book1_r2` 做“是否适合检验统计水平”的筛选结果（586 行）。
- `variables_processing_report.txt` / `exercise_judgment_report.txt`：变量抽取与筛选的汇总报告。
- `process_log.txt` / `process_variables_log.txt` / `judge_exercises_log.txt`：运行日志（含时间戳、错误原因、重试信息）。

核心脚本与提示词：

- `process_book1.py`：`book1 -> book1_r1`（重编排：背景 + 子问题列表 + 方法标签）。
- `get_data.py`：`book1_r1 -> data0_book1.json/.pkl`（扁平化每个子问题为单条样本）。
- `split_json.py`：`data0_book1.json -> book1_r2/*.json`（逐条拆分）。
- `process_variables.py`：对 `book1_r2/*.json` 抽取变量，写回 `output.variable`。
- `judge_exercises.py`：对 `book1_r2/*.json` 进行筛选打分，输出 `exercise_judgments.csv`。
- `prompt.py`：三套提示词（`prompt_gen_0`/`prompt_gen_1`/`prompt_check_0`）。

## 3. 已实现的处理流程与结果

### 3.1 方法类别标签初步预测及习题重编排（`book1 -> book1_r1`）
考虑到原来从教材中提取的一个题目，可能包含多个子问题及答案，我们首先考虑将不同子问题拆开，并利用llm根据每个子问题的问答给出该样本的方法类别标签"method"。每个子问题的{"query", "answer", "method"}构成了task的一个元素。

脚本：`process_book1.py` + `prompt.py::prompt_gen_0`

做了什么：

- 从原始 `record_*.json` 中抽取 `question`、`answer`，让 LLM 生成新结构：
  - `background`：背景描述
  - `task[]`：子问题列表，每个子问题含 `query`、`answer`、`method`
- 同时保留/合并原始的 `id`、`data`、`meta info` 字段到输出。
- 为应对原始文件“非严格 JSON”的情况，采用正则读取器（`read_json_file()`）而非直接 `json.load()`。

当前工作区的结果：

- `book1/`：292 个原始文件
- `book1_r1/`：277 个重编排输出
- 缺失（未成功产出 `book1_r1` 对应文件）的 15 个原始记录：
  - `record_021.json`, `record_076.json`, `record_116.json`, `record_127.json`, `record_142.json`
  - `record_152.json`, `record_153.json`, `record_372.json`, `record_378.json`, `record_418.json`
  - `record_427.json`, `record_440.json`, `record_448.json`, `record_449.json`, `record_452.json`

过程记录：

- `process_log.txt`：包含大量原始文件解析错误（例如 `Invalid \\uXXXX escape`）与运行期异常信息。
- `book1_r1/processing_report.txt`：记录某次尝试处理一小波数据时，成功/失败情况统计与失败具体原因。

### 3.2 子问题扁平化生成样本（`book1_r1 -> data0_book1.json/.pkl`）
将前面重编排后的 `book1_r1` 中的每个 `task[]` 子问题展开为单条样本，形成一个新的聚合数据文件。

脚本：`get_data.py`

做了什么：

- 遍历 `book1_r1/record_*.json` 的 `task[]`，把每个子问题展开为单条样本：
  - `case_id`：源 `record_*.json` 文件路径
  - `input`: `{background, data, question}`
  - `output`: `{method, answer}`
  - `meta_info`：原始元信息（章节、页码等）

当前工作区的结果：

- `data0_book1.json` / `data0_book1.pkl`：共 588 条样本，key 范围 `1..588`。

### 3.3 按条拆分为单文件（`data0_book1.json -> book1_r2/*.json`）
将上一步生成的 `data0_book1.json` 中的每条样本单独保存为一个 JSON 文件，便于后续逐条处理（如变量抽取、筛选等）。

脚本：`split_json.py`

做了什么：

- 将 `data0_book1.json` 的每个条目保存为 `book1_r2/{sample_key}.json`，并写入 `sample_key` 字段。

NOTE：
- 理论条数：`data0_book1.json` 有 588 条
- 当前 `book1_r2/`：586 个 `*.json`
- 缺失的样本文件（同时也不在 `exercise_judgments.csv` 中）：`14.json`、`224.json`

### 3.4 变量抽取（写回 `output.variable`）

脚本：`process_variables.py` + `prompt.py::prompt_gen_1`（变量抽取提示词）

做了什么：

- 提取 `book1_r2/*.json` 的 `input`（background/data/question），与prompt拼接后，调用 LLM 抽取变量集合。
- 将模型输出解析为 JSON，并写回到每个样本的 `output.variable` 字段。
- 报告文件：`variables_processing_report.txt`（时间戳：2026-03-30 22:41:54）

当前工作区的结果（以磁盘现有 586 个样本文件统计）：

- `book1_r2/*.json` 共 586 个
- 其中已有 `output.variable`：573 个
- 缺失 `output.variable`：13 个（这些样本文件仍在，但变量字段未写入）：
  - `32.json`, `34.json`, `36.json`, `38.json`, `62.json`
  - `187.json`, `276.json`, `347.json`, `351.json`
  - `353.json`, `354.json`, `581.json`, `583.json`

与筛选结果的关系（用于后续“保留题目”处理优先级）：

- `judge=1`（适合保留）的 346 条中，有 340 条已具备 `output.variable`
- `judge=1` 但缺失 `output.variable` 的 6 条样本 ID：
  - `34`, `187`, `276`, `347`, `353`, `354`

失败原因（来自 `variables_processing_report.txt`）主要是：

- 模型输出无法解析为严格 JSON（例如出现注释 `// ...`、省略号 `...`、或输出夹带自然语言解释）。
- 个别样本 `input` 信息不足，模型直接返回“信息不完整”的文本答复。

### 3.5 习题筛选（是否适合检验统计水平）

脚本：`judge_exercises.py` + `prompt.py::prompt_check_0`

筛选标准（提示词定义）：

- 判为不适合（`judge=0`）的两类典型情况：
  - 过于基础或简单：只识别数据/概念定义等，不足以检验统计能力。
  - 难以理解/无法独立作答：题干不清楚，或依赖未提供的图/上下文/其他题结论。
- 判为适合（`judge=1`）则 `explanation` 固定填 `无`。

当前工作区的结果（`exercise_judgments.csv`）：

- 总行数：586（对应 `book1_r2` 现存样本）
- `judge=1`：346 条
- `judge=0`：240 条

报告文件：

- `exercise_judgment_report.txt`（时间戳：2026-04-02 15:51:58，报告显示当次运行 586/586 成功）

## 4. 单条样本的当前字段形态（用于你快速理解产物）

路径：`book1_r2/{id}.json`

现有字段（典型）：

- `sample_key`：样本编号（字符串）
- `case_id`：来源 `book1_r1\\record_XXX.json`
- `input.background` / `input.data` / `input.question`
- `output.answer`
- `output.method`：在重编排阶段生成的统计方法类别（来自 `prompt_gen_0` 的方法框架）
- `output.variable`：变量抽取结果（若成功）
- `meta_info`：章节/小节/页码等

## 5. 已知问题与后续缺口

我们需要完成的目标是“先筛选有实际应用背景的问答对，再对剩余样本用 LLM 预测统计方法类别与所需变量 label 作为评测标签”。就现状而言：

### 主要问题：
- 方法标签：当前 `output.method` 是在 `process_book1.py` 阶段由 LLM 基于（question+answer）生成的“方法类别”。如果后续评测需要新的方法 taxonomy 或更严格的标签一致性，可能需要在 `judge=1` 子集上重新打标。
- 变量标签：当前已有 `output.variable`（变量抽取与角色/类型等），但完全根据input抽取，不能作为“用于评测的变量信息的 label”。
### 次要问题：
- 数据完整性：
  - `book1_r2` 中缺失 `14`、`224` 两条样本（同时 `exercise_judgments.csv` 也缺这两条）。
  - 仍有 13 条样本未成功写入 `output.variable`；其中 6 条属于 `judge=1`，会影响后续在“保留题目子集”上做变量 label 的覆盖率。
- 样本筛选：v0已实现一版“是否适合检验统计水平”的自动筛选（`exercise_judgments.csv`），但尚不等价于“是否有实际应用背景”。如果希望严格筛“应用背景题”，需要重新设计/细化筛选提示词与判定维度。
- 路径问题：脚本中大量使用 Windows 绝对路径（如 `d:\\place\\study\\bookassign\\...`），建议统一改为相对路径或基于项目根目录的路径。

# v1已完成工作梳理

## 目标:
将变量与方法标签的生成改为“生成→审阅→修正”的可迭代流水线（侧重可检验与可追溯）。
为了便于复现与 prompt 调试，不再直接改写 `book1_r2/*.json`，而是新建一个独立目录 `label_construct/` 来组织 v1 的代码和结果。

## 主要思路
### 方法审阅
调用llm(gpt4o)，对现有 output.method 做一致性审阅，产出审阅意见供人工/后续分析（不直接改写标签）。
### 变量抽取
1. 优先基于 answer 的实际求解过程抽取“实际被使用的变量对象”（包括汇总统计量、差值、列联表等）。每个变量要求 id、value、class、role、description（便于评测与人工复核）。
2. 多轮审阅与修正: 抽取后用第二轮 LLM 审阅；若不准确则按审阅意见修正，循环至准确或达轮次上限。
3. 结果保存: 按轮次保存（round_0/、round_1/ … final/），保留每轮样本与审阅记录，便于溯源与错误归因。
4. 容错性: 抽取或审阅失败时保留占位结果并写审阅状态，保证 final/ 覆盖全部输入样本。


## 当前通过case study(20条样本)发现的主要问题
v1 目前已经能产出结构化结果，但质量仍存在明显问题。

### method 审阅
典型错误包括：

- 一些本来 method 就有误的样本，没有被 method review 识别出来；
- 某些样本虽然给出了修改意见，但修改方向并不合理；
- 现有 taxonomy 对少数检验方法覆盖不够，导致 LLM 很难稳定落到合适类别。

这说明：

- 现有 taxonomy 对边缘统计方法的覆盖还不够；
- 仅靠一次 LLM 审阅，仍存在一定漏检率。

### 变量抽取
1. role 判断仍然是变量抽取中最不稳定的部分
2. value 提取和变量范围识别仍不稳定

## 整体判断
1. prompt 调整已经带来改进，但边际收益开始下降

## 后续更新计划
1. 尝试更强的模型
2. 尝试用多个模型进行审阅，以求降低漏检率
3. 继续优化 prompt，针对高频错误类型建立专门规则
4. 在 method 审阅结果更可靠之后，完善 method taxonomy

# v2已完成工作梳理

## 目标
将标签构建流程从 case study 式的小规模试跑，扩展为可直接覆盖全部教材样本目录的稳定流水线，并把“方法标签”和“变量标签”都独立保存到 `label_construct/results_final/<目录名>/` 下，便于分书追踪、缓存复用和后续人工检查。

## 主要思路

### 1. 多目录批量运行
- `label_construct/run_pipeline.py` 现在支持通过 `--input-dirs` 传入一个或多个样本目录，例如 `book1_r3 book2_r3 ...`
- 流水线会对这些目录逐个串行处理，每个目录独立生成自己的结果目录、日志和摘要
- 不同教材目录之间不共享最终结果路径，避免缓存和输出互相覆盖

### 2. 方法标签改为独立 CSV 管理
- 方法审阅结果统一写入 `label_construct/results_final/<目录名>/method_review/method_review.csv`
- 每条记录包含 `sample_key`、`case_id`、`suggested_method`、`proposed_new_category`、`reason`
- `suggested_method` 统一要求为 `一级类目名\二级类目名`
- 对旧缓存中的仅二级类目结果，先根据 `METHOD_TAXONOMY_TEXT` 做自动补全；只有在二级类目唯一归属于某个一级类目时才自动改写
- 方法审阅缓存规则支持两种模式：
  - `--update_method true`：只把格式完整的 `一级\二级` 标签视为命中缓存
  - `--update_method false`：只要 `sample_key` 已存在于 `method_review.csv` 就视为命中缓存

### 3. 变量标签按“主模型抽取 + 可选建议模型 + 终审”组织
- `variable_extract` 会先生成主模型的 `round_0` 变量标签
- 如果提供 `model_suggest`，会额外生成 suggest 模型的 `round_0` 结果，供后续终审参考
- `variable_finalize` 由主模型综合 major/suggest 两份结果，决定是否修改，并把最终版本写入 `variable_labels/final/`
- 如果没有提供 `model_suggest`，则直接把 major 的 `round_0` 复制到 `final`

### 4. 结果与日志按目录隔离
- 每个输入目录都会生成独立的：
  - `method_review/`
  - `variable_labels/`
  - `logs/`
  - `runs/summary.json`
- `summary.json` 中记录当前输入目录、模型、阶段、样本数、缓存情况和 token 使用量，方便后续统计
- `logs/*.log` 用于定位具体样本的失败原因，例如 JSON 解析失败、标签格式错误、变量缺失等

### 5. 当前版本工作流的整体特点
- 不再回写原始样本 JSON，标签结果与原始数据分离
- 以“目录级别批处理 + 样本级缓存 + 日志级溯源”为主线
- 方法标签和变量标签都支持部分重跑与强制覆盖
- 已能支撑 `book*_r3` 全量样本的初步打标与复查
