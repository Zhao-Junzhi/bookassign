#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对exercise_judgments.csv文件中前100行judge=1的样本进行改写处理
"""

import os
import json
import re
import time
import logging
import asyncio
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# 导入OpenAI库
try:
    import openai
except ImportError:
    import pip
    pip.main(['install', 'openai'])
    import openai

# 导入API配置和提示词
from api_info import api_key, base_url
from prompt import prompt_phrase

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rewrite_exercises_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置参数
INPUT_CSV = Path(r'd:\place\study\bookassign\exercise_judgments.csv')
OUTPUT_CSV = Path(r'd:\place\study\bookassign\rewritten_exercises.csv')
MAX_WORKERS = 5  # 并行处理的线程数
API_RATE_LIMIT = 0.5  # API调用间隔（秒）
MAX_RETRIES = 3  # 最大重试次数
MAX_SAMPLES = 100  # 处理前100个样本

# 配置OpenAI客户端
openai.api_key = api_key
if base_url:
    openai.api_base = base_url

class APIError(Exception):
    """API调用错误"""
    pass

async def call_gpt4o_async(prompt: str) -> str:
    """
    异步调用GPT-5 API
    
    Args:
        prompt: 提示词
        
    Returns:
        API返回的内容
        
    Raises:
        APIError: API调用失败
    """
    for attempt in range(MAX_RETRIES):
        try:
            # 使用OpenAI SDK 1.0+的异步方法
            client = openai.AsyncClient(
                api_key=api_key,
                base_url=base_url
            )
            
            response = await client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=120
            )
            return response.choices[0].message.content
            
        except Exception as e:
            # 通用异常处理
            error_message = str(e)
            if "rate limit" in error_message.lower():
                wait_time = (attempt + 1) * 2
                logger.warning(f"API限流，等待{wait_time}秒后重试...")
                await asyncio.sleep(wait_time)
            elif "timeout" in error_message.lower():
                logger.warning(f"请求超时，第{attempt + 1}次重试...")
                await asyncio.sleep(2)
            else:
                logger.error(f"API调用异常: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                else:
                    raise APIError(f"API调用失败: {e}")
    
    raise APIError("超过最大重试次数")

def parse_model_output(content: str) -> Dict:
    """
    解析模型输出，提取JSON部分
    
    Args:
        content: 模型返回的原始内容
        
    Returns:
        解析后的JSON字典
    """
    # 首先尝试提取JSON代码块（优先处理markdown格式）
    json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    matches = re.findall(json_pattern, content, re.DOTALL)
    
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    
    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # 尝试匹配最外层的大括号
    try:
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start:end+1])
    except json.JSONDecodeError:
        pass
    
    raise Exception(f"无法从模型输出中解析JSON: {content[:200]}...")

async def evaluate_output(original: Dict, rewritten: Dict) -> Tuple[bool, str]:
    """
    Evaluate if the model output meets the requirements
    
    Args:
        original: Original data
        rewritten: Rewritten data
        
    Returns:
        (whether it meets requirements, feedback)
    """
    try:
        # Build evaluation prompt
        evaluation_prompt = f"""
Please evaluate whether the following rewritten statistical consulting case meets the requirements:

Original data:
{json.dumps(original, ensure_ascii=False)}

Rewritten data:
{json.dumps(rewritten, ensure_ascii=False)}

Evaluation requirements:
1. Rewrite from the perspective of a client seeking statistical consulting, avoiding excessive statistical jargon
2. Use "we" as the subject
3. Keep all numerical values, names, and contextual details unchanged
4. If mathematical formulas are included, they must be displayed using LaTeX code
5. Output format should be JSON containing "background" and "question" fields

Please determine if the rewritten content meets the above requirements and provide specific modification suggestions.

Output format:
{{
  "satisfies": true/false,
  "feedback": "modification suggestions"
}}
"""
        
        # Call API for evaluation
        evaluation_response = await call_gpt4o_async(evaluation_prompt)
        evaluation_result = parse_model_output(evaluation_response)
        
        satisfies = evaluation_result.get('satisfies', True)
        feedback = evaluation_result.get('feedback', '')
        
        return satisfies, feedback
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return True, "Evaluation process error, using original output"

async def process_single_sample(sample: Dict, semaphore: asyncio.Semaphore) -> Tuple[Dict, bool, str]:
    """
    处理单个样本
    
    Args:
        sample: 样本数据
        semaphore: 信号量控制并发
        
    Returns:
        (结果数据, 是否成功, 错误信息)
    """
    async with semaphore:
        try:
            original_background = sample.get('background', '')
            original_question = sample.get('question', '')
            
            logger.info(f"开始处理样本: {original_question[:50]}...")
            
            # 构建提示词
            input_data = {
                "background": original_background,
                "question": original_question
            }
            input_text = json.dumps(input_data, ensure_ascii=False)
            prompt = prompt_phrase + input_text
            
            # 调用API
            response_content = await call_gpt4o_async(prompt)
            
            # 解析模型输出
            rewritten = parse_model_output(response_content)
            
            # 评估输出是否满足要求
            original_data = {
                "background": original_background,
                "question": original_question
            }
            satisfies, feedback = await evaluate_output(original_data, rewritten)
            
            # If it doesn't meet requirements, regenerate based on feedback
            if not satisfies:
                logger.info(f"Output doesn't meet requirements, regenerating based on feedback: {feedback}...")
                
                # Build correction prompt
                correction_prompt = f"""
Your previous output doesn't meet the requirements. Please revise it based on the following feedback:

{feedback}

Original data:
{json.dumps(original_data, ensure_ascii=False)}

Please regenerate output that meets all requirements, formatted as JSON with "background" and "question" fields.
"""
                
                # Call API for correction
                correction_response = await call_gpt4o_async(correction_prompt)
                rewritten = parse_model_output(correction_response)
            
            # 构建结果数据
            result = {
                'original_background': original_background,
                'original_question': original_question,
                'rewritten_background': rewritten.get('background', ''),
                'rewritten_question': rewritten.get('question', '')
            }
            
            logger.info(f"成功处理样本")
            
            # 添加延迟以控制API调用频率
            await asyncio.sleep(API_RATE_LIMIT)
            
            return result, True, ""
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"处理失败: {error_msg}")
            # 即使失败也返回原始数据，保持数据完整性
            result = {
                'original_background': sample.get('background', ''),
                'original_question': sample.get('question', ''),
                'rewritten_background': '',
                'rewritten_question': ''
            }
            return result, False, error_msg

def read_csv_file() -> List[Dict]:
    """
    读取CSV文件，筛选出judge=1的样本
    
    Returns:
        筛选后的样本列表
    """
    samples = []
    
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('judge') == '1':
                    samples.append(row)
                if len(samples) >= MAX_SAMPLES:
                    break
        
        logger.info(f"从CSV文件中筛选出 {len(samples)} 个judge=1的样本")
        return samples
        
    except Exception as e:
        logger.error(f"读取CSV文件失败: {e}")
        return []

async def process_samples():
    """
    处理样本的主函数
    """
    # 读取并筛选样本
    samples = read_csv_file()
    total_samples = len(samples)
    
    logger.info(f"找到 {total_samples} 个judge=1的样本待处理")
    logger.info(f"输入CSV文件: {INPUT_CSV}")
    logger.info(f"输出CSV文件: {OUTPUT_CSV}")
    
    if total_samples == 0:
        logger.warning("没有找到judge=1的样本")
        return
    
    # 统计信息
    success_count = 0
    failed_samples = []
    results = []
    
    # 使用信号量控制并发数
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    
    # 创建任务列表
    tasks = [
        process_single_sample(sample, semaphore)
        for sample in samples
    ]
    
    # 处理所有任务
    start_time = time.time()
    
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        result, success, error_msg = await coro
        
        if success:
            success_count += 1
        else:
            failed_samples.append((i, error_msg))
        
        results.append(result)
        
        # 每处理10个样本输出一次进度
        if (i + 1) % 10 == 0 or (i + 1) == total_samples:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info(f"进度: {i + 1}/{total_samples} ({(i + 1) / total_samples * 100:.1f}%), "
                       f"成功: {success_count}, 失败: {len(failed_samples)}, "
                       f"速度: {rate:.2f} 样本/秒")
    
    # 保存结果到CSV文件
    save_results_to_csv(results)
    
    # 生成处理报告
    elapsed_time = time.time() - start_time
    generate_report(total_samples, success_count, failed_samples, elapsed_time)

def save_results_to_csv(results: List[Dict]):
    """
    将结果保存到CSV文件
    
    Args:
        results: 处理结果列表
    """
    try:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['original_background', 'original_question', 'rewritten_background', 'rewritten_question']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"结果已保存到: {OUTPUT_CSV}")
    except Exception as e:
        logger.error(f"保存CSV文件失败: {e}")

def generate_report(total: int, success: int, failed: List[Tuple[int, str]], elapsed: float):
    """
    生成处理报告
    
    Args:
        total: 总样本数
        success: 成功数
        failed: 失败样本列表
        elapsed: 耗时（秒）
    """
    report = []
    report.append("=" * 60)
    report.append("习题改写处理报告")
    report.append("=" * 60)
    report.append(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"总耗时: {elapsed:.2f} 秒")
    report.append(f"总样本数: {total}")
    report.append(f"成功处理: {success}")
    report.append(f"处理失败: {len(failed)}")
    report.append(f"成功率: {success / total * 100:.2f}%" if total > 0 else "N/A")
    report.append("")
    
    if failed:
        report.append("失败样本列表:")
        report.append("-" * 60)
        for sample_idx, error in failed:
            report.append(f"  - 样本 {sample_idx}: {error}")
    else:
        report.append("所有样本处理成功！")
    
    report.append("=" * 60)
    
    report_text = "\n".join(report)
    
    # 使用UTF-8编码打印
    try:
        print("\n" + report_text)
    except UnicodeEncodeError:
        print("\n报告包含特殊字符，请查看文件中的详细内容")
    
    # 保存报告到文件
    report_path = INPUT_CSV.parent / 'rewrite_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    logger.info(f"报告已保存到: {report_path}")

def main():
    """
    主函数
    """
    logger.info("=" * 60)
    logger.info("开始处理exercise_judgments.csv中的样本")
    logger.info(f"API URL: {base_url}")
    logger.info(f"并发数: {MAX_WORKERS}")
    logger.info(f"API调用间隔: {API_RATE_LIMIT}秒")
    logger.info(f"处理前{MAX_SAMPLES}个judge=1的样本")
    logger.info("=" * 60)
    
    # 运行异步处理
    asyncio.run(process_samples())

if __name__ == '__main__':
    main()
