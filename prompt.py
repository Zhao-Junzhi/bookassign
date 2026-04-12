prompt_gen_0 = '''

你是一个专业的统计学教师，需要对统计学教材习题进行重新编，将其拆分为问题背景和多个子任务。你获取到的统计学教材习题是由规范化的JSON格式呈现的，相关字段的含义为。
- question：完整的问题描述（可能包含多个子问题）
- answer：参考答案

需将该统计学教材习题整理为新的JSON格式，形如
{
"background":"从原来question字段中提取的问题背景描述。",
"task":[
{
"query":"从原来question字段中提取的第一个子问题",
"answer":"从原来answer字段中提取的第一个子问题的对应答案"
},
{
"query":"从原来question字段中提取的第二个子问题（如果存在的话）",
"answer":"从原来answer字段中提取的第二个子问题的对应答案（如果存在的话）"
},
{
"query":"从原来question字段中提取的第三个子问题（如果存在的话）",
"answer":"从原来answer字段中提取的第三个子问题的对应答案（如果存在的话）"
},
……
],
}

注意："background"，"query"，"answer"字段仍用英文表述。
下面，请按要求处理给出的统计学教材习题：

'''

prompt_gen_1 = '''
你是一个专业的统计学教师。
你需要从统计学习题及其数据中提取解决这道题所需数据变量。
统计学习题由以下三个字段组成：

"background"：问题背景
"data"：数据，通常是latex代码形式的表格数据。这部分只呈现结构化或者能够系统性表示的数据，其他数据也可能蕴含在"background"或"question"中
"question"：核心问题

你需要提取该问题中用到的所有变量，每一个变量用一个单独的JSON格式表示，形式如下：
{
"id": "变量名（提取自题目或自行指定合适的变量名）",
"value": "变量取值（如果是表格数据的某一列，需在此处以列表形式记录该列所有的值）",
"class": "变量类别（数值型记为"numerical"、分类型记为"categorical"）",
"role": "变量在题目中的角色",
"description": "对该变量的简要描述"
}

注意：各字段均用英文表述。

变量对象不要求对应题目中的显式变量名，也可以是：
- 原始数据表中的某一列；
- 一组分组统计量；
- 一个列联表；
- 其它在解答中实际被调用的数据对象。

"role"的字段的变量角色，是指各变量在统计模型中的作用，分为以下四类：
        （1）independent（自变量），是指由研究者主动操纵或自然存在的、不受其他变量影响的变量。它是引起其他变量变化的原因或条件。此处用于构造自变量的原始变量也属于该角色。
        （2）dependent（因变量），是因为自变量的变化而被引起变化的变量。它是研究者观察和测量的结果。此处用于构造因变量的原始变量也属于该角色。
        （3）both（自变量和因变量二者兼备），是指研究两个（多个）变量之间的相关性但没有区分因果的必要或该变量兼具因果两种角色。
        （4）NR（不必指定角色），是指在分析中不必区分因变量和自变量，一般包括以下几种情况：
            - 仅作为样本标识或索引的变量，因需要匹配多个数据集的样本而必须纳入相关变量（variable）集合的。
            - 仅作用于筛选部分样本进行分析（如研究2020年的数据时的“年份”变量）的变量而必须纳入相关变量（variable）集合的。
            - 无监督方法（聚类、降维）涉及的相关变量。
            - 仅研究变量的分布情况或时间序列的平稳性时涉及的相关变量。

        特殊情况：
            - 对于“数据可视化“中的“时间变化趋势”类问题，需要将表示时间概念的变量作为independent，随时间变化的变量作为dependent（即使变量集合中未出现时间变量）。例如，研究不同时间点的销售量变化趋势，时间变量作为independent，销售量变量作为dependent。
            - 如果一个变量既作为自变量又用于构造因变量，该变量的角色为independent。
            - 如果一个变量既作为因变量又用于构造自变量，该变量的角色为dependent。
    - 流程（answer），即用一段完整的话描述用上述统计模型或方法应用于这个问题的全流程。

请将所有相关变量对应的JSON格式描述合在一起，将"id"字段的内容作为key，输出完整的JSON。
'''

prompt_check_0='''
你是一个专业的统计学老师，你需要判断统计学练习题是否适用于检测学生的统计学水平，统计学习题以如下JSON格式给出：

{
    "background": "问题背景",
    "data": "解决问题需要用到的数据（可能为空）",
    "question": "问题描述",
    "answer": "问题的对应答案"
}

以下题目认应视为不适合检测学生的统计学水平的题目：

- 过于基础或简单的问题，包括：
	- 仅要求识别某个数据。
	- 仅要求解释某个基本概念的含义或直接考察学生对某个基本概念的理解（但不包括绘制图表或需进行数学计算的问题）。

- 难以理解的问题，包括：
	- 问题描述含糊不清，无法理解，或并没有具体的问题。
	- 该题目需要用到其他题目的解答结果或重要信息，而这些重要信息在该题目的题干和数据中并未体现。

- 答案这个字段的内容为空的问题。

注：部分题目中提到的表格（table）在“data”字段中以latex代码呈现，这种情况不能认为表格缺失。

判断结果以如下JSON格式输出：

{
  "judge": "评判结果（1或0，1代表适合，0代表不适合）",
  "explanation": "作出判断的理由，如果认为该题目适合，则仅不需要给出理由，该字段填入'无'即可。"
}

'''

prompt_phrase='''
You are a textbook author for a course on Statistical Consulting. You will be given an exercise from another statistics textbook and need to rewrite it as a case study for your Statistical Consulting textbook. The exercise consists of two fields: "background" and "question", which respectively describe the context and the core problem of the exercise.

The key point of the rewrite is to rephrase the "background" and "question" in the style of a client seeking statistical consulting. These clients are typically practitioners in their respective fields, so the output should avoid excessive statistical jargon. You need to appropriately rewrite the statistical terminology from the original problem to make it intuitive and easy to understand, without changing the core meaning.

Example Transformation:
Input:
"Most people have an intuitive sense of how probabilities work. Here is a passage from Woody Guthrie's autobiography Bound for Glory‘ that demonstrates clear probabilistic reasoning: A kid named Bud run the gambling wheel. It was an old lopsided bicycle wheel that he had found in the dumps and tried to even up. He paid you ten to one if you called off the right spoke it would stop on. But there was sixty spokes. Draw a graph of the probability density function curve for Bud’s gambling wheel. Assume the bicycle wheel has been evened up to create a uniform distribution for values between $1$ and $60$. 

Output:
"Most people have an intuitive sense of how probabilities work. Here is a passage from Woody Guthrie's autobiography Bound for Glory‘ that demonstrates clear probabilistic reasoning: A kid named Bud run the gambling wheel. It was an old lopsided bicycle wheel that he had found in the dumps and tried to even up. He paid you ten to one if you called off the right spoke it would stop on. But there was sixty spokes. Intuitively display the distribution of gambling returns.



Note:
- Please do not indicate the specific name of the statistical model in the 'question' or 'background' fields, and avoid using overly technical statistical terms.
- The rewritten problem should be from the client's perspective, as a query from the client, so the subject should typically be "we".
- Keep all numerical values, names, and contextual details unchanged.
- If the output includes mathematical formulas, they must be displayed using LaTeX code.
- Output in JSON format, containing two fields: "background" and "question", which are the rewritten versions of the original "background" and "question" respectively.
'''