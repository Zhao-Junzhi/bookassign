import os
import json
import pickle
import csv
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from prompt import Prompt_question_4

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('process_data.log'),
        logging.StreamHandler()
    ]
)


def load_data(file_path):
    """
    加载JSON数据
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"成功加载数据文件: {file_path}")
        logging.info(f"数据包含 {len(data)} 个样本")
        return data
    except Exception as e:
        logging.error(f"加载数据失败: {str(e)}")
        raise


def call_openai_api(task_description, analysis_report, api_key=None, model="gpt-4o", max_retries=3):
    """
    调用OpenAI API
    """
    if api_key is None:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("OpenAI API key not provided")
    
    client = OpenAI(api_key=api_key, base_url="https://toollearning.cn/v1")
    
    messages = [
        {
            "role": "system",
            "content": "你是一个经验丰富的统计学教师，擅长分析学生的数据分析报告。"
        },
        {
            "role": "user",
            "content": f"{Prompt_question_4}\n\n任务描述：\n{json.dumps(task_description, ensure_ascii=False, indent=2)}\n\n数据分析报告：\n{json.dumps(analysis_report, ensure_ascii=False, indent=2)}"
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


def process_data(data, api_key, max_workers=5):
    """
    处理数据
    """
    processed_data = {}
    total_samples = len(data)
    
    def process_sample(key, sample):
        """
        处理单个样本
        """
        try:
            # 提取任务描述和分析报告
            task_description = sample.get("input", {})
            analysis_report = sample.get("output", {})
            
            if not task_description:
                logging.warning(f"样本 {key} 缺少 input 字段")
                return key, sample
            
            if not analysis_report:
                logging.warning(f"样本 {key} 缺少 output 字段")
                return key, sample
            
            # 调用API
            result = call_openai_api(task_description, analysis_report, api_key)
            
            # 保持原始结构，仅替换output字段
            processed_sample = sample.copy()
            processed_sample["output"] = result
            
            logging.info(f"样本 {key} 处理成功")
            return key, processed_sample
            
        except Exception as e:
            logging.error(f"处理样本 {key} 失败: {str(e)}")
            # 保存原始样本
            return key, sample
    
    # 使用线程池并行处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {executor.submit(process_sample, key, sample): key for key, sample in data.items()}
        
        # 处理完成的任务
        for i, future in enumerate(as_completed(futures), 1):
            key = futures[future]
            try:
                sample_key, processed_sample = future.result()
                processed_data[sample_key] = processed_sample
                logging.info(f"完成处理样本 {i}/{total_samples}: {sample_key}")
            except Exception as e:
                logging.error(f"获取结果时出错: {str(e)}")
                # 保存原始样本
                processed_data[key] = data[key]
    
    return processed_data


def save_data(data, json_path, pkl_path, csv_path):
    """
    保存数据
    """
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
    
    # 保存为CSV
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow(['key', 'case_id', 'input', 'output'])
            # 写入数据
            for key, sample in sorted_data.items():
                case_id = sample.get('case_id', '')
                input_data = json.dumps(sample.get('input', {}), ensure_ascii=False)
                output_data = json.dumps(sample.get('output', {}), ensure_ascii=False)
                writer.writerow([key, case_id, input_data, output_data])
        logging.info(f"成功保存为CSV文件: {csv_path}")
    except Exception as e:
        logging.error(f"保存CSV文件失败: {str(e)}")
        raise


def main():
    # 文件路径
    input_file = r"D:\place\study\LLMabstract\data_gen\data0.json"
    output_json = r"D:\place\study\LLMabstract\data_gen\data0_processed.json"
    output_pkl = r"D:\place\study\LLMabstract\data_gen\data0_processed.pkl"
    output_csv = r"D:\place\study\LLMabstract\data_gen\data0_processed.csv"
    
    # API密钥
    api_key = "sk-7w19nykEjVHl6rmMn0rCoxyUWJbAuzZhnYP9zvMGQPNzqg32"
    
    try:
        # 加载数据
        data = load_data(input_file)
        
        # 处理数据
        processed_data = process_data(data, api_key, max_workers=10)
        
        # 保存数据
        save_data(processed_data, output_json, output_pkl, output_csv)
        
        logging.info("处理完成!")
        
    except Exception as e:
        logging.error(f"处理过程中出现错误: {str(e)}")
        raise


if __name__ == "__main__":
    main()
