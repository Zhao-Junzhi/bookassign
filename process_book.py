#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理book12345目录下的JSON文件，使用GPT-4o进行统计学教材习题重新编排
"""

import os
import json
import re
import time
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from prompt import prompt_gen_0

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('process_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置参数
INPUT_DIR = Path(r'd:\place\study\bookassign\book5')
OUTPUT_DIR = Path(r'd:\place\study\bookassign\book5_r1')
MAX_WORKERS = 8  # 并行处理的线程数
API_RATE_LIMIT = 0.5  # API调用间隔（秒）
MAX_RETRIES = 3  # 最大重试次数

# 配置OpenAI客户端
openai.api_key = api_key
if base_url:
    openai.api_base = base_url

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class APIError(Exception):
    """API调用错误"""
    pass


class JSONParseError(Exception):
    """JSON解析错误"""
    pass


def read_json_file(file_path: Path) -> Optional[Dict]:
    """
    使用正则表达式解析类JSON文件，处理格式不规范问题
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        解析后的字典，失败返回None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除BOM标记
        if content.startswith('\ufeff'):
            content = content[1:]
        
        result = {}
        
        # 提取 id 字段
        id_match = re.search(r'"id"\s*:\s*"([^"]*)"', content)
        if id_match:
            result['id'] = id_match.group(1)
        
        # 提取 question 字段（可能包含换行）
        question_match = re.search(r'"question"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
        if question_match:
            result['question'] = question_match.group(1)
        
        # 提取 data 字段（可能包含复杂的LaTeX代码、换行或null值）
        data_match = re.search(r'"data"\s*:\s*(null|"((?:[^"\\]|\\.)*)")', content, re.DOTALL)
        if data_match:
            if data_match.group(1) == 'null':
                result['data'] = None
            else:
                data_content = data_match.group(2)
                # 处理转义字符
                data_content = data_content.replace('\\n', '\n')
                data_content = data_content.replace('\\t', '\t')
                data_content = data_content.replace('\\r', '\r')
                data_content = data_content.replace('\\"', '"')
                data_content = data_content.replace('\\\\', '\\')
                result['data'] = data_content
        
        # 提取 answer 字段
        answer_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
        if answer_match:
            answer_content = answer_match.group(1)
            # 处理转义字符
            answer_content = answer_content.replace('\\n', '\n')
            answer_content = answer_content.replace('\\t', '\t')
            answer_content = answer_content.replace('\\"', '"')
            answer_content = answer_content.replace('\\\\', '\\')
            result['answer'] = answer_content
        
        # 提取 meta info 字段（嵌套对象）
        meta_match = re.search(r'"meta_info"\s*:\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', content, re.DOTALL)
        if meta_match:
            meta_content = meta_match.group(0)
            meta_info = {}
            
            # 提取 index
            index_match = re.search(r'"index"\s*:\s*"([^"]*)"', meta_content)
            if index_match:
                meta_info['index'] = index_match.group(1)
            
            # 提取 img_in_question
            img_in_question_match = re.search(r'"img_in_question"\s*:\s*(null|"([^"]*)")', meta_content)
            if img_in_question_match:
                if img_in_question_match.group(1) == 'null':
                    meta_info['img_in_question'] = None
                else:
                    meta_info['img_in_question'] = img_in_question_match.group(2)
            
            # 提取 img_in_answer
            img_in_answer_match = re.search(r'"img_in_answer"\s*:\s*(null|"([^"]*)")', meta_content)
            if img_in_answer_match:
                if img_in_answer_match.group(1) == 'null':
                    meta_info['img_in_answer'] = None
                else:
                    meta_info['img_in_answer'] = img_in_answer_match.group(2)
            
            # 提取 caption
            caption_match = re.search(r'"caption"\s*:\s*(null|"([^"]*)")', meta_content)
            if caption_match:
                if caption_match.group(1) == 'null':
                    meta_info['caption'] = None
                else:
                    meta_info['caption'] = caption_match.group(2)
            
            # 提取 chapter
            chapter_match = re.search(r'"chapter"\s*:\s*"([^"]*)"', meta_content)
            if chapter_match:
                meta_info['chapter'] = chapter_match.group(1)
            
            # 提取 section
            section_match = re.search(r'"section"\s*:\s*"([^"]*)"', meta_content)
            if section_match:
                meta_info['section'] = section_match.group(1)
            
            # 提取 book
            book_match = re.search(r'"book"\s*:\s*"([^"]*)"', meta_content)
            if book_match:
                meta_info['book'] = book_match.group(1)
            
            # 提取 page
            page_match = re.search(r'"page"\s*:\s*"([^"]*)"', meta_content)
            if page_match:
                meta_info['page'] = page_match.group(1)
            
            result['meta_info'] = meta_info
        
        return result
        
    except Exception as e:
        logger.error(f"文件读取错误 {file_path.name}: {e}")
        raise JSONParseError(f"文件解析错误: {e}")


def extract_fields(data: Dict) -> Tuple[str, str, Dict]:
    """
    从JSON数据中提取question和answer字段
    
    Args:
        data: JSON数据字典
        
    Returns:
        (question, answer, meta_info) 元组
    """
    question = data.get('question', '')
    answer = data.get('answer', '')
    
    # 保留原始字段
    original_fields = {
        'id': data.get('id', ''),
        'data': data.get('data', ''),
        'meta_info': data.get('meta_info', {})
    }
    
    if not question:
        logger.warning("question字段为空")
    if not answer:
        logger.warning("answer字段为空")
        
    return question, answer, original_fields


def build_prompt(question: str, answer: str) -> str:
    """
    构建完整的提示词
    
    Args:
        question: 问题内容
        answer: 答案内容
        
    Returns:
        完整的提示词字符串
    """
    user_content = f"""
question: {question}

answer: {answer}
"""
    return prompt_gen_0 + user_content


async def call_gpt4o_async(prompt: str, session=None) -> str:
    """
    异步调用GPT-4o API
    
    Args:
        prompt: 提示词
        session: 未使用，为了保持接口一致
        
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
    import re
    
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
    
    raise JSONParseError(f"无法从模型输出中解析JSON: {content[:200]}...")


def merge_output(model_output: Dict, original_fields: Dict) -> Dict:
    """
    将原始字段合并到模型输出中
    
    Args:
        model_output: 模型输出的JSON
        original_fields: 原始字段
        
    Returns:
        合并后的JSON
    """
    result = model_output.copy()
    
    # 添加原始字段
    result['id'] = original_fields['id']
    result['data'] = original_fields['data']
    result['meta_info'] = original_fields['meta_info']
    
    return result


def save_json_file(data: Dict, file_path: Path) -> None:
    """
    保存JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 保存路径
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存: {file_path.name}")
    except Exception as e:
        logger.error(f"保存文件失败 {file_path.name}: {e}")
        raise


async def process_single_file(file_path: Path, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore) -> Tuple[str, bool, str]:
    """
    处理单个文件
    
    Args:
        file_path: 文件路径
        session: aiohttp会话
        semaphore: 信号量控制并发
        
    Returns:
        (文件名, 是否成功, 错误信息)
    """
    async with semaphore:
        try:
            logger.info(f"开始处理: {file_path.name}")
            
            # 读取JSON文件
            data = read_json_file(file_path)
            if data is None:
                return file_path.name, False, "读取文件失败"
            
            # 提取字段
            question, answer, original_fields = extract_fields(data)
            
            # 构建提示词
            prompt = build_prompt(question, answer)
            
            # 调用API
            response_content = await call_gpt4o_async(prompt, session)
            
            # 解析模型输出
            model_output = parse_model_output(response_content)
            
            # 合并输出
            final_output = merge_output(model_output, original_fields)
            
            # 保存结果
            output_path = OUTPUT_DIR / file_path.name
            save_json_file(final_output, output_path)
            
            logger.info(f"成功处理: {file_path.name}")
            
            # 添加延迟以控制API调用频率
            await asyncio.sleep(API_RATE_LIMIT)
            
            return file_path.name, True, ""
            
        except JSONParseError as e:
            logger.error(f"JSON解析错误 {file_path.name}: {e}")
            return file_path.name, False, str(e)
        except APIError as e:
            logger.error(f"API错误 {file_path.name}: {e}")
            return file_path.name, False, str(e)
        except Exception as e:
            logger.error(f"处理失败 {file_path.name}: {e}")
            return file_path.name, False, str(e)


async def process_all_files():
    """
    处理所有文件的主函数
    """
    # 获取所有JSON文件
    json_files = sorted(INPUT_DIR.glob('*.json'))
    
    # 过滤掉已经处理过的文件
    existing_files = set(f.name for f in OUTPUT_DIR.glob('*.json'))
    unprocessed_files = [f for f in json_files if f.name not in existing_files]
    
    total_files = len(unprocessed_files)
    
    logger.info(f"找到 {len(json_files)} 个JSON文件")
    logger.info(f"已处理 {len(json_files) - total_files} 个文件，剩余 {total_files} 个文件待处理")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    
    if total_files == 0:
        logger.warning("没有找到需要处理的JSON文件")
        return
    
    # 统计信息
    success_count = 0
    failed_files = []
    
    # 使用信号量控制并发数
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    
    # 创建任务列表
    tasks = [
        process_single_file(file_path, None, semaphore)
        for file_path in unprocessed_files
    ]
    
    # 处理所有任务
    start_time = time.time()
    
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        file_name, success, error_msg = await coro
        
        if success:
            success_count += 1
        else:
            failed_files.append((file_name, error_msg))
        
        # 每处理10个文件输出一次进度
        if (i + 1) % 10 == 0 or (i + 1) == total_files:
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
    report.append("处理报告")
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
    report_path = OUTPUT_DIR / 'processing_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    logger.info(f"报告已保存到: {report_path}")


def main():
    """
    主函数
    """
    logger.info("=" * 60)
    logger.info("开始处理book1目录下的JSON文件")
    logger.info(f"API URL: {base_url}")
    logger.info(f"并发数: {MAX_WORKERS}")
    logger.info(f"API调用间隔: {API_RATE_LIMIT}秒")
    logger.info("=" * 60)
    
    # 运行异步处理
    asyncio.run(process_all_files())


if __name__ == '__main__':
    main()
