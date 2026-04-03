#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理book1_r2目录中的前十个JSON文件，提取变量信息
"""

import os
import json
import re
import time
import logging
import asyncio
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
from prompt import prompt_gen_1

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('process_variables_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置参数
INPUT_DIR = Path(r'd:\place\study\bookassign\book1_r2')
MAX_WORKERS = 5  # 并行处理的线程数
API_RATE_LIMIT = 0.5  # API调用间隔（秒）
MAX_RETRIES = 3  # 最大重试次数

# 配置OpenAI客户端
openai.api_key = api_key
if base_url:
    openai.api_base = base_url

class APIError(Exception):
    """API调用错误"""
    pass

async def call_gpt4o_async(prompt: str) -> str:
    """
    异步调用GPT-4o API
    
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
                model="gpt-4o",
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

async def process_single_file(file_path: Path, semaphore: asyncio.Semaphore) -> Tuple[str, bool, str]:
    """
    处理单个文件
    
    Args:
        file_path: 文件路径
        semaphore: 信号量控制并发
        
    Returns:
        (文件名, 是否成功, 错误信息)
    """
    async with semaphore:
        try:
            logger.info(f"开始处理: {file_path.name}")
            
            # 读取JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取input字段
            input_data = data.get('input', {})
            if not input_data:
                return file_path.name, False, "input字段为空"
            
            # 构建提示词
            input_text = f"background: {input_data.get('background', '')}\n"
            input_text += f"data: {input_data.get('data', '')}\n"
            input_text += f"question: {input_data.get('question', '')}"
            
            prompt = prompt_gen_1 + input_text
            
            # 调用API
            response_content = await call_gpt4o_async(prompt)
            
            # 解析模型输出
            variables = parse_model_output(response_content)
            
            # 更新原数据
            if 'output' not in data:
                data['output'] = {}
            data['output']['variable'] = variables
            
            # 保存更新后的数据
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功处理: {file_path.name}")
            
            # 添加延迟以控制API调用频率
            await asyncio.sleep(API_RATE_LIMIT)
            
            return file_path.name, True, ""
            
        except Exception as e:
            logger.error(f"处理失败 {file_path.name}: {e}")
            return file_path.name, False, str(e)

async def process_files():
    """
    处理所有文件的主函数
    """
    # 获取所有JSON文件
    json_files = sorted(INPUT_DIR.glob('*.json'))
    total_files = len(json_files)
    
    logger.info(f"找到 {total_files} 个JSON文件待处理")
    logger.info(f"输入目录: {INPUT_DIR}")
    
    if total_files == 0:
        logger.warning("没有找到JSON文件")
        return
    
    # 统计信息
    success_count = 0
    failed_files = []
    
    # 使用信号量控制并发数
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    
    # 创建任务列表
    tasks = [
        process_single_file(file_path, semaphore)
        for file_path in json_files
    ]
    
    # 处理所有任务
    start_time = time.time()
    
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        file_name, success, error_msg = await coro
        
        if success:
            success_count += 1
        else:
            failed_files.append((file_name, error_msg))
        
        # 每处理一个文件输出一次进度
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        logger.info(f"进度: {i + 1}/{total_files} ({(i + 1) / total_files * 100:.1f}%), "
                   f"成功: {success_count}, 失败: {len(failed_files)}, "
                   f"速度: {rate:.2f} 文件/秒")
    
    # 生成处理报告
    elapsed_time = time.time() - start_time
    generate_report(total_files, success_count, failed_files, elapsed_time)

def generate_report(total: int, success: int, failed: List[Tuple[str, str]], elapsed: float):
    """
    生成处理报告
    
    Args:
        total: 总文件数
        success: 成功数
        failed: 失败文件列表
        elapsed: 耗时（秒）
    """
    report = []
    report.append("=" * 60)
    report.append("变量提取处理报告")
    report.append("=" * 60)
    report.append(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
    report_path = INPUT_DIR.parent / 'variables_processing_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    logger.info(f"报告已保存到: {report_path}")

def main():
    """
    主函数
    """
    logger.info("=" * 60)
    logger.info("开始处理book1_r2目录中的所有JSON文件")
    logger.info(f"API URL: {base_url}")
    logger.info(f"并发数: {MAX_WORKERS}")
    logger.info(f"API调用间隔: {API_RATE_LIMIT}秒")
    logger.info("=" * 60)
    
    # 运行异步处理
    asyncio.run(process_files())

if __name__ == '__main__':
    main()
