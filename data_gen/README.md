
## 核心处理脚本

### 1. main.py
**主程序入口**：协调整个数据处理流程，包括调用html_processor处理HTML文件、quality_checker检查结果质量、result_modifier根据反馈修改结果。支持批量处理data_list目录下的所有子文件夹。

### 2. batch_process_html.py
**批量HTML处理脚本**：批量处理data_list目录下所有子文件夹中的HTML文件，提取文本内容并调用OpenAI API生成query0.json。包含token使用统计功能。

### 3. html_processor.py
**HTML处理器**：从HTML文件中提取文本内容，调用OpenAI API（使用Prompt_question_1）生成结构化的JSON结果。返回处理结果和token使用信息。

### 4. process_query0_to_query1.py
**Query0转Query1处理器**：将query0.json（包含学生答案的数据分析报告）转换为query1.json（包含统计方法分类）。使用Prompt_question_2调用API进行方法分类。

### 5. format_questions.py
**问题格式化工具**：从HTML文件中提取文本内容，调用OpenAI API使用Prompt_question_1生成标准化的数据分析任务描述。

### 6. quality_checker.py
**质量检查器**：使用Prompt_question_3检查生成的结果是否符合统计学原则和数据质量要求。返回验证结果和修改意见。

### 7. result_modifier.py
**结果修改器**：根据quality_checker提供的反馈意见，调用API修改生成的结果，使其符合质量要求。

### 8. match_variable_roles.py
**变量角色匹配器**：为data0.json中每个样本的variable字段匹配对应的role字段（X/Y/both/NR）。调用大模型API根据统计学原理判断各变量的角色。