import os
import json
from openai import OpenAI
from prompt import Prompt_question_1


def modify_result_with_feedback(result_json, feedback, report_content, dataset_description=None, api_key=None, model="gpt-4o"):
    """
    根据修改意见修改结果
    
    参数:
        result_json: 当前结果
        feedback: 修改意见
        report_content: HTML报告内容
        dataset_description: 数据集描述
        api_key: API密钥
        model: 模型名称
    
    返回:
        (modified_result, usage_info) 元组
    """
    if api_key is None:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
    
    client = OpenAI(api_key=api_key, base_url="https://toollearning.cn/v1")
    
    # 构建修改prompt
    result_text = json.dumps(result_json, ensure_ascii=False, indent=2)
    user_content = Prompt_question_1 + "\n\n数据分析报告内容：\n" + report_content
    
    # 添加案例所需数据集情况部分
    if dataset_description:
        user_content += "\n\n案例所需数据集情况：\n" + dataset_description
    else:
        user_content += "\n\n该案例未提供JSON格式的所需数据集情况。"
    
    user_content += "\n\n之前生成的结果：\n" + result_text
    
    # 处理feedback可能是列表的情况
    if isinstance(feedback, list):
        feedback_str = "\n".join([str(item) for item in feedback])
    else:
        feedback_str = str(feedback)
    
    user_content += "\n\n修改意见：\n" + feedback_str
    user_content += "\n\n请根据修改意见修改上述结果，返回符合要求的JSON格式。"
    
    messages = [
        {
            "role": "system",
            "content": "你是一位经验丰富的统计学教师，擅长设计数据分析任务。"
        },
        {
            "role": "user",
            "content": user_content
        }
    ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        modified_text = response.choices[0].message.content
        modified_result = json.loads(modified_text)
        
        # 获取token使用信息
        usage_info = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        return modified_result, usage_info
    
    except json.JSONDecodeError as e:
        print(f"修改结果JSON解析错误: {e}")
        print(f"返回内容: {modified_text}")
        raise
    except Exception as e:
        print(f"修改结果API调用错误: {e}")
        raise
