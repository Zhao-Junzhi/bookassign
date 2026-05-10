import json
import pickle
import os
import sys
import concurrent.futures
from openai import OpenAI
import logging
import time
from datetime import datetime

# 添加父目录到路径以导入api_info
sys.path.insert(0, r'd:\place\study\Consulting-Agent')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='rewrite_process.log'
)

from api_info import api_key, base_url

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

def load_prompt_templates():
    """加载提示词模板"""
    try:
        with open(r'd:\place\study\Consulting-Agent\改写\prompt.py', 'r', encoding='utf-8') as f:
            content = f.read()
        local_vars = {}
        exec(content, local_vars)
        return local_vars['prompt_rewrite'], local_vars['prompt_think'], local_vars['quality_check_prompt']
    except Exception as e:
        logging.error(f"加载提示词模板失败: {e}")
        raise e

def call_model(messages, model="gpt-5.4"):
    """调用大模型API"""
    try:
        for msg in messages:
            if 'content' in msg and (not msg['content'] or msg['content'].strip() == ''):
                raise ValueError("消息内容不能为空")
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3
        )
        usage = response.usage
        return response.choices[0].message.content.strip(), {
            'prompt_tokens': usage.prompt_tokens,
            'completion_tokens': usage.completion_tokens,
            'total_tokens': usage.total_tokens
        }
    except ValueError as ve:
        logging.error(f"消息验证失败: {ve}")
        raise ve
    except Exception as e:
        logging.error(f"API调用失败: {e}")
        raise e

def process_sample(sample_key, sample, prompt_rewrite, prompt_think, quality_check_prompt):
    """处理单个样本的三个阶段"""
    result = {
        'sample_key': sample_key,
        'original_input': sample.get('input', {}),
        'original_output': sample.get('output', {}),
        'rewrite_stage': {},
        'think_stage': {},
        'revision_stages': [],
        'final_result': None,
        'success': False,
        'total_tokens': 0
    }

    input_data = sample.get('input', {})
    output_data = sample.get('output', {})

    if not input_data or not output_data:
        result['error'] = "输入数据或输出数据为空"
        logging.error(f"样本 {sample_key} 的输入或输出数据为空")
        return sample_key, result

    original_input_output = json.dumps({
        'input': input_data,
        'output': output_data
    }, ensure_ascii=False)
    
    if not original_input_output or len(original_input_output.strip()) < 10:
        result['error'] = "序列化后的输入输出数据过短"
        logging.error(f"样本 {sample_key} 的序列化数据过短: {original_input_output}")
        return sample_key, result

    try:
        # 阶段1: 改写
        rewrite_messages = [
            {"role": "system", "content": prompt_rewrite + f"\n\n---\n\nPlease rewrite the following statistical problem:\n\n{original_input_output}"}
        ]
        rewritten_text, rewrite_tokens = call_model(rewrite_messages)
        result['rewrite_stage'] = {
            'output': rewritten_text,
            'tokens': rewrite_tokens
        }
        result['total_tokens'] += rewrite_tokens['total_tokens']

        # 阶段2: 思考
        think_messages = [
            {"role": "system", "content": prompt_think + f"\n\n---\n\nPlease analyze the following statistical problem:\n\n{original_input_output}"}
        ]
        think_result, think_tokens = call_model(think_messages)
        result['think_stage'] = {
            'output': think_result,
            'tokens': think_tokens
        }
        result['total_tokens'] += think_tokens['total_tokens']

        # 阶段3: 循环返修
        current_rewritten = rewritten_text
        max_revisions = 3

        for revision_num in range(max_revisions):
            # 质量检查
            check_messages = [
                {"role": "system", "content": quality_check_prompt + f"\n\n---\n\nOriginal input-output:\n{original_input_output}\n\nThe reason for deriving this statistical model from the original problem is\n{think_result}\n\nRewritten problem:\n{current_rewritten}"}
            ]
            check_result, check_tokens = call_model(check_messages)
            result['total_tokens'] += check_tokens['total_tokens']

            # 解析检查结果
            try:
                check_json = json.loads(check_result)
                pass_check = check_json.get('pass', False)
                feedback = check_json.get('feedback', '')
            except:
                pass_check = False
                feedback = "Failed to parse check result"

            revision_record = {
                'revision_num': revision_num + 1,
                'check_result': check_result,
                'check_pass': pass_check,
                'feedback': feedback,
                'tokens': check_tokens
            }
            result['revision_stages'].append(revision_record)

            if pass_check:
                result['success'] = True
                result['final_result'] = current_rewritten
                break
            else:
                # 再次改写
                if revision_num < max_revisions - 1:
                    retry_messages = [
                        {"role": "system", "content": prompt_rewrite + f"\n\n---\n\nOriginal input-output:\n{original_input_output}\n\nPrevious rewrite:\n{current_rewritten}\n\nFeedback:\n{feedback}\n\nPlease provide a new rewrite that addresses the feedback."}
                    ]
                    current_rewritten, retry_tokens = call_model(retry_messages)
                    result['total_tokens'] += retry_tokens['total_tokens']

                    revision_record['retry_output'] = current_rewritten
                    revision_record['retry_tokens'] = retry_tokens
                else:
                    # 三次后仍未通过，保留原始input
                    result['final_result'] = json.dumps({
                        'background': input_data.get('background', ''),
                        'question': input_data.get('question', '')
                    }, ensure_ascii=False)

    except Exception as e:
        logging.error(f"处理样本 {sample_key} 时出错: {e}")
        result['error'] = str(e)

    return sample_key, result

def save_progress(data, output_file):
    """保存处理进度"""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"进度已保存到 {output_file}")
    except Exception as e:
        logging.error(f"保存进度失败: {e}")

def process_json_file(input_file, output_file, log_file):
    """处理JSON文件"""
    try:
        # 加载提示词模板
        prompt_rewrite, prompt_think, quality_check_prompt = load_prompt_templates()

        # 检查断点文件
        if os.path.exists(output_file):
            logging.info("检测到已存在的输出文件，尝试断点续传...")
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            processed_keys = set(data.keys())
        else:
            data = {}
            processed_keys = set()

        # 读取输入文件
        logging.info(f"读取文件 {input_file}")
        with open(input_file, 'rb') as f:
            input_data = pickle.load(f)

        # 筛选未处理的样本
        unprocessed_samples = {k: v for k, v in input_data.items() if k not in processed_keys}

        if not unprocessed_samples:
            logging.info("所有样本已经处理完成！")
            print("所有样本已经处理完成！")
            return

        logging.info(f"发现 {len(unprocessed_samples)} 个样本需要处理")
        print(f"发现 {len(unprocessed_samples)} 个样本需要处理")

        # 使用线程池并行处理
        max_workers = 3
        processed_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {
                executor.submit(process_sample, key, sample, prompt_rewrite, prompt_think, quality_check_prompt): key
                for key, sample in unprocessed_samples.items()
            }

            for future in concurrent.futures.as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    sample_key, result = future.result()
                    data[sample_key] = result
                    processed_count += 1

                    # 每处理1个样本保存一次进度
                    if processed_count % 1 == 0:
                        save_progress(data, output_file)
                        logging.info(f"已完成 {processed_count}/{len(unprocessed_samples)} 个样本的处理")
                        print(f"已完成 {processed_count}/{len(unprocessed_samples)} 个样本的处理")
                except Exception as e:
                    logging.error(f"处理样本 {key} 时出错: {e}")

        # 最后保存一次完整结果
        save_progress(data, output_file)

        # 保存token统计
        total_tokens = sum(r.get('total_tokens', 0) for r in data.values())
        token_summary = {
            'total_samples': len(data),
            'total_tokens': total_tokens,
            'avg_tokens_per_sample': total_tokens / len(data) if data else 0,
            'processed_at': datetime.now().isoformat()
        }

        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(token_summary, f, ensure_ascii=False, indent=2)

        logging.info(f"处理完成！共处理 {processed_count} 个样本")
        print(f"处理完成！共处理 {processed_count} 个样本，结果保存到 {output_file}")
        print(f"Token统计已保存到 {log_file}")

    except Exception as e:
        logging.error(f"处理文件时出错: {e}")
        print(f"处理文件时出错: {e}")

def main():
    input_file = r'd:\place\study\Consulting-Agent\改写\data_in_book_processed.pkl'
    output_file = r'd:\place\study\Consulting-Agent\改写\data_in_book_rewritten3.json'
    log_file = r'd:\place\study\Consulting-Agent\改写\rewrite_token_log3.json'

    process_json_file(input_file, output_file, log_file)

if __name__ == "__main__":
    main()