import json
import os
from pathlib import Path
from bs4 import BeautifulSoup
from openai import OpenAI
from prompt import Prompt_question_1


def extract_text_from_html(html_file_path):
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    return text


def call_openai_api(report_content, api_key=None, model="gpt-4o"):
    if api_key is None:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
    
    client = OpenAI(api_key=api_key, base_url="https://toollearning.cn/v1")
    
    messages = [
        {
            "role": "system",
            "content": "你是一位经验丰富的统计学教师，擅长设计数据分析任务。"
        },
        {
            "role": "user",
            "content": Prompt_question_1 + "\n\n数据分析报告内容：\n" + report_content
        }
    ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)
        return result_json
    
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"返回内容: {result_text}")
        raise
    except Exception as e:
        print(f"API调用错误: {e}")
        raise


def process_html_report(html_file_path=None, output_json_path=None, api_key=None, model="gpt-4o"):
    report_content = extract_text_from_html(html_file_path)
    
    result = call_openai_api(report_content, api_key, model)
    
    if output_json_path:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {output_json_path}")
    
    return result


if __name__ == "__main__":
    
    result = process_html_report(
        html_file_path="数据代码PPT(cleaned)_v0/数据代码PPT(cleaned)_v0/探索性数据分析/有一种玩具，适合3-99岁所有人群/doc&code/任务文档-教师版.html",
        output_json_path="数据代码PPT(cleaned)_v0/数据代码PPT(cleaned)_v0/探索性数据分析/有一种玩具，适合3-99岁所有人群/doc&code/任务文档-教师版.json",
        api_key="sk-47cMhQHFxQn6MqoYB0800eE0F6F14e878c93Bb0a6337D98e",
        model="gpt-4o"
    )
    
    print("\n处理结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
