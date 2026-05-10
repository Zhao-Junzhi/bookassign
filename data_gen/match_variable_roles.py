import os
import json
import pickle
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('match_role.log'),
        logging.StreamHandler()
    ]
)

ROLE_PROMPT = '''
你是一个统计学专家，擅长分析数据分析报告中变量的角色。

任务描述：
{background}

数据描述：
{data_description}

核心问题：
{question}

学生提交的数据分析报告中涉及的变量：
{variable}

变量角色判断标准：
1. X（自变量）：由研究者主动操纵或自然存在的、不受其他变量影响的变量。它是引起其他变量变化的原因或条件。此处用于构造自变量的原始变量也属于该角色。
2. Y（因变量）：因为自变量的变化而被引起变化的变量。它是研究者观察和测量的结果。此处用于构造因变量的原始变量也属于该角色。
3. both（自变量和因变量二者兼备）：研究两个（多个）变量之间的相关性但没有区分因果的必要或该变量兼具因果两种角色。
4. NR（不必指定角色）：在分析中不必区分因变量和自变量，一般包括以下几种情况：
   - 仅作为样本标识或索引的变量
   - 仅作用于筛选部分样本进行分析的变量
   - 无监督方法（聚类、降维）涉及的相关变量
   - 仅研究变量的分布情况或时间序列的平稳性时涉及的相关变量

特殊情况：
- 对于"数据可视化"中的"时间变化趋势"类问题，需要将表示时间概念的变量作为X，随时间变化的变量作为Y。
- 如果一个变量既作为自变量又用于构造因变量，该变量的角色为X。
- 如果一个变量既作为因变量又用于构造自变量，该变量的角色为Y。

请根据以上信息，判断每个变量的角色，返回JSON格式结果，格式如下：
{{
    "数据集文件名": {{
        "角色1",
        "角色2"
    }}
}}

其中角色只能是：X、Y、both、NR 之一。
'''


def load_data(file_path):
    """加载JSON数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"成功加载数据文件: {file_path}")
        logging.info(f"数据包含 {len(data)} 个样本")
        return data
    except Exception as e:
        logging.error(f"加载数据失败: {str(e)}")
        raise


def call_openai_api(task_description, api_key=None, model="gpt-4o", max_retries=3):
    """调用OpenAI API"""
    if api_key is None:
        api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        raise ValueError("OpenAI API key not provided")

    client = OpenAI(api_key=api_key, base_url="https://toollearning.cn/v1")

    messages = [
        {
            "role": "system",
            "content": "你是一个统计学专家，擅长分析数据分析报告中变量的角色。"
        },
        {
            "role": "user",
            "content": task_description
        }
    ]

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            logging.info(f"API调用成功，尝试次数: {attempt + 1}")
            return result

        except json.JSONDecodeError as e:
            logging.error(f"JSON解析错误: {e}")
            logging.error(f"返回内容: {result_text}")
            if attempt == max_retries - 1:
                raise
        except Exception as e:
            logging.error(f"API调用错误: {e}")
            if attempt == max_retries - 1:
                raise
            logging.info(f"等待3秒后重试...")
            time.sleep(3)


def match_variable_roles(sample, api_key):
    """为单个样本的variable字段匹配role"""
    try:
        # 提取必要信息
        case_id = sample.get('case_id', '')
        input_data = sample.get('input', {})
        output_data = sample.get('output', {})

        background = input_data.get('background', '')
        data_description_1 = input_data.get('data_description_1', '')
        data_description_2 = input_data.get('data_description_2', {})
        question = input_data.get('question', '')
        variable = output_data.get('variable', {})

        if not variable:
            logging.warning(f"样本 {case_id} 缺少 variable 字段")
            return None

        # 构建prompt
        prompt = ROLE_PROMPT.format(
            background=background,
            data_description=json.dumps(data_description_2, ensure_ascii=False, indent=2),
            question=question,
            variable=json.dumps(variable, ensure_ascii=False, indent=2)
        )

        # 调用API
        result = call_openai_api(prompt, api_key)
        return result

    except Exception as e:
        logging.error(f"匹配变量角色失败: {str(e)}")
        return None


def process_data(data, api_key, max_workers=10):
    """处理数据"""
    processed_data = {}
    total_samples = len(data)

    def process_sample(key, sample):
        """处理单个样本"""
        try:
            case_id = sample.get('case_id', '')
            logging.info(f"处理样本: {key}, case_id: {case_id}")

            # 调用API匹配role
            role_result = match_variable_roles(sample, api_key)

            # 保持原始结构，添加role字段
            processed_sample = sample.copy()
            if role_result:
                if 'output' not in processed_sample:
                    processed_sample['output'] = {}
                processed_sample['output']['role'] = role_result
                logging.info(f"样本 {key} 匹配成功")
            else:
                logging.warning(f"样本 {key} 匹配失败，保留原始数据")

            return key, processed_sample

        except Exception as e:
            logging.error(f"处理样本 {key} 失败: {str(e)}")
            return key, sample

    # 使用线程池并行处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_sample, key, sample): key for key, sample in data.items()}

        for i, future in enumerate(as_completed(futures), 1):
            key = futures[future]
            try:
                sample_key, processed_sample = future.result()
                processed_data[sample_key] = processed_sample
                logging.info(f"完成处理样本 {i}/{total_samples}: {sample_key}")
            except Exception as e:
                logging.error(f"获取结果时出错: {str(e)}")
                processed_data[key] = data[key]

    return processed_data


def save_data(data, json_path, pkl_path):
    """保存数据"""
    # 按key的数字顺序排序
    sorted_data = dict(sorted(data.items(), key=lambda x: int(x[0])))

    # 保存为JSON
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        logging.info(f"成功保存为JSON文件: {json_path}")
    except Exception as e:
        logging.error(f"保存JSON文件失败: {str(e)}")
        raise

    # 保存为PKL
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(sorted_data, f)
        logging.info(f"成功保存为PKL文件: {pkl_path}")
    except Exception as e:
        logging.error(f"保存PKL文件失败: {str(e)}")
        raise


def main():
    # 文件路径
    input_file = r"D:\place\study\LLMabstract\data_gen\data0.json"
    output_json = r"D:\place\study\LLMabstract\data_gen\data0_with_role.json"
    output_pkl = r"D:\place\study\LLMabstract\data_gen\data0_with_role.pkl"

    # API密钥
    api_key = "sk-7w19nykEjVHl6rmMn0rCoxyUWJbAuzZhnYP9zvMGQPNzqg32"

    try:
        # 加载数据
        data = load_data(input_file)

        # 处理数据
        processed_data = process_data(data, api_key, max_workers=10)

        # 保存数据
        save_data(processed_data, output_json, output_pkl)

        logging.info("处理完成!")

    except Exception as e:
        logging.error(f"处理过程中出现错误: {str(e)}")
        raise


if __name__ == "__main__":
    main()
