#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
判断统计学习题是否符合要求，并将结果保存为CSV文件
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
from prompt import prompt_check_0

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('judge_exercises_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置参数
BASE_DIR = Path(r'd:\place\study\bookassign')
BOOKS = [1, 2, 3, 4, 5]  # 要处理的书的编号
MAX_WORKERS = 8  # 并行处理的线程数
API_RATE_LIMIT = 0.5  # API调用间隔（秒）
MAX_RETRIES = 3  # 最大重试次数

# 配置OpenAI客户端
openai.api_key = api_key
if base_url:
    openai.api_base = base_url

class APIError(Exception):
    """API调用错误"""
    pass

async def call_gpt4o_async(prompt: str) -> Tuple[str, Dict]:
    """
    
    Args:
        prompt: 提示词
        
    Returns:
        (API返回的内容, token使用量)
        
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
                model="claude-sonnet-4-6",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=120,
                response_format={"type": "json_object"}
            )
            # 获取token使用量
            token_usage = response.usage.to_dict() if response.usage else {}
            return response.choices[0].message.content, token_usage
            
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

async def process_single_file(file_path: Path, semaphore: asyncio.Semaphore, output_dir: Path) -> Tuple[str, Dict, bool, str]:
    """
    处理单个文件
    
    Args:
        file_path: 文件路径
        semaphore: 信号量控制并发
        output_dir: 输出目录
        
    Returns:
        (文件名, 结果数据, 是否成功, 错误信息)
    """
    async with semaphore:
        try:
            logger.info(f"开始处理: {file_path.name}")
            
            # 读取JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取所需字段
            sample_key = data.get('sample_key', '')
            case_id = data.get('case_id', '')
            input_data = data.get('input', {})
            output_data = data.get('output', {})
            answer = output_data.get('answer', '')
            background = input_data.get('background', '')
            data_content = input_data.get('data', '')
            question = input_data.get('question', '')
            
            if not input_data:
                return file_path.name, {}, False, "input字段为空"
            
            # 构建标准格式的input_text，确保包含四个字段
            standard_input = {
                "background": background,
                "data": data_content,
                "question": question,
                "answer": answer
            }
            input_text = json.dumps(standard_input, ensure_ascii=False)
            prompt = prompt_check_0 + input_text
            
            # 调用API
            response_content, token_usage = await call_gpt4o_async(prompt)
            
            # 解析模型输出
            judgment = parse_model_output(response_content)
            
            # 构建结果数据
            result = {
                'sample_key': sample_key,
                'case_id': case_id,
                'background': background,
                'data': data_content,
                'question': question,
                'judge': judgment.get('judge', ''),
                'explanation': judgment.get('explanation', ''),
                'token_usage': token_usage
            }
            
            # 如果judge为1，保存对应的JSON文件到输出目录，并添加token使用情况
            if result.get('judge') == '1':
                # 复制原始数据并添加token使用情况
                output_data = data.copy()
                output_data['token_usage'] = token_usage
                
                output_json_path = output_dir / file_path.name
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                logger.info(f"已保存judge为1的文件: {file_path.name}")
                logger.info(f"Token使用量: {token_usage}")
            
            logger.info(f"成功处理: {file_path.name}")
            
            # 添加延迟以控制API调用频率
            await asyncio.sleep(API_RATE_LIMIT)
            
            return file_path.name, result, True, ""
            
        except Exception as e:
            logger.error(f"处理失败 {file_path.name}: {e}")
            return file_path.name, {}, False, str(e)

async def process_files(input_dir: Path, output_dir: Path):
    """
    处理指定目录中的所有文件
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录
    """
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取所有JSON文件
    json_files = sorted(input_dir.glob('*.json'))
    total_files = len(json_files)
    
    output_csv = output_dir / 'exercise_judgments.csv'
    
    logger.info(f"找到 {total_files} 个JSON文件待处理")
    logger.info(f"输入目录: {input_dir}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"输出CSV文件: {output_csv}")
    
    if total_files == 0:
        logger.warning("没有找到JSON文件")
        return
    
    # 统计信息
    success_count = 0
    failed_files = []
    results = []
    
    # 使用信号量控制并发数
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    
    # 创建任务列表
    tasks = [
        process_single_file(file_path, semaphore, output_dir)
        for file_path in json_files
    ]
    
    # 处理所有任务
    start_time = time.time()
    
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        file_name, result, success, error_msg = await coro
        
        if success:
            success_count += 1
            results.append(result)
        else:
            failed_files.append((file_name, error_msg))
        
        # 每处理10个文件输出一次进度
        if (i + 1) % 10 == 0 or (i + 1) == total_files:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info(f"进度: {i + 1}/{total_files} ({(i + 1) / total_files * 100:.1f}%), "
                       f"成功: {success_count}, 失败: {len(failed_files)}, "
                       f"速度: {rate:.2f} 文件/秒")
    
    # 保存结果到CSV文件
    save_results_to_csv(results, output_csv)
    
    # 生成处理报告
    elapsed_time = time.time() - start_time
    generate_report(total_files, success_count, failed_files, elapsed_time, input_dir, output_dir)

def save_results_to_csv(results: List[Dict], output_csv: Path):
    """
    将结果保存到CSV文件
    
    Args:
        results: 处理结果列表
        output_csv: 输出CSV文件路径
    """
    try:
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['sample_key', 'case_id', 'background', 'data', 'question', 'judge', 'explanation', 'token_usage']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"结果已保存到: {output_csv}")
    except Exception as e:
        logger.error(f"保存CSV文件失败: {e}")

def generate_report(total: int, success: int, failed: List[Tuple[str, str]], elapsed: float, input_dir: Path, output_dir: Path):
    """
    生成处理报告
    
    Args:
        total: 总文件数
        success: 成功数
        failed: 失败文件列表
        elapsed: 耗时（秒）
        input_dir: 输入目录
        output_dir: 输出目录
    """
    report = []
    report.append("=" * 60)
    report.append("习题判断处理报告")
    report.append("=" * 60)
    report.append(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"输入目录: {input_dir}")
    report.append(f"输出目录: {output_dir}")
    report.append(f"总耗时: {elapsed:.2f} 秒")
    report.append(f"总文件数: {total}")
    report.append(f"成功处理: {success}")
    report.append(f"处理失败: {len(failed)}")
    report.append(f"成功率: {success / total * 100:.2f}%" if total > 0 else "N/A")
    report.append("")
    
    if failed:
        report.append("失败文件列表:")
        report.append("-" * 60)
        for file_name, error in failed:
            report.append(f"  - {file_name}: {error}")
    else:
        report.append("所有文件处理成功！")
    
    report.append("=" * 60)
    
    report_text = "\n".join(report)
    
    # 使用UTF-8编码打印
    try:
        print("\n" + report_text)
    except UnicodeEncodeError:
        print("\n报告包含特殊字符，请查看文件中的详细内容")
    
    # 保存报告到文件
    report_path = output_dir / 'exercise_judgment_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    logger.info(f"报告已保存到: {report_path}")

def main():
    """
    主函数
    """
    logger.info("=" * 60)
    logger.info("开始判断目录中的所有统计学习题")
    logger.info(f"API URL: {base_url}")
    logger.info(f"并发数: {MAX_WORKERS}")
    logger.info(f"API调用间隔: {API_RATE_LIMIT}秒")
    logger.info("=" * 60)
    
    # 循环处理每个目录
    for book in BOOKS:
        input_dir = BASE_DIR / f'book{book}_r2'
        output_dir = BASE_DIR / f'book{book}_r3'
        
        logger.info(f"\n处理 book{book}_r2 目录...")
        logger.info(f"输入目录: {input_dir}")
        logger.info(f"输出目录: {output_dir}")
        
        # 运行异步处理
        asyncio.run(process_files(input_dir, output_dir))
        
        logger.info(f"book{book}_r2 目录处理完成！")
        logger.info("-" * 60)

if __name__ == '__main__':
    main()
