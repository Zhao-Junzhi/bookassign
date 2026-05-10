import os
import json
from openai import OpenAI
from prompt import Prompt_question_3


def check_result_quality(result_json, api_key=None, model="gpt-4o"):
    """
    使用Prompt_question_3检查生成结果是否符合原则
    
    参数:
        result_json: 生成的JSON结果
        api_key: API密钥
        model: 模型名称
    
    返回:
        (is_valid, feedback, usage_info) 元组
        is_valid: 是否符合原则
        feedback: 修改意见（如果不符合）
        usage_info: token使用信息
    """
    if api_key is None:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
    
    client = OpenAI(api_key=api_key, base_url="https://toollearning.cn/v1")
    
    # 构建检查prompt
    result_text = json.dumps(result_json, ensure_ascii=False, indent=2)
    user_content = Prompt_question_3 + "\n\n待检查的数据分析任务：\n" + result_text + "\n\n请判断是否符合上述原则，如果符合请返回{\"is_valid\": true}，如果不符合请返回{\"is_valid\": false, \"feedback\": \"具体修改意见\"}"
    
    messages = [
        {
            "role": "system",
            "content": "你是一位经验丰富的统计学教师，擅长评估数据分析任务的质量。"
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
        
        check_result_text = response.choices[0].message.content
        check_result = json.loads(check_result_text)
        
        # 获取token使用信息
        usage_info = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        is_valid = check_result.get("is_valid", False)
        feedback = check_result.get("feedback", "")
        
        return is_valid, feedback, usage_info
    
    except json.JSONDecodeError as e:
        print(f"检查结果JSON解析错误: {e}")
        print(f"返回内容: {check_result_text}")
        return False, "检查结果解析失败", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    except Exception as e:
        print(f"检查结果API调用错误: {e}")
        return False, "检查过程出错", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
