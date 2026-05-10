import os
import json
from pathlib import Path
from openai import OpenAI
from prompt import Prompt_question_2


def call_openai_api_with_tokens(query0_content, api_key=None, model="gpt-4o"):
    """
    调用OpenAI API并返回结果和token使用信息
    
    参数:
        query0_content: query0.json的内容（不包含token_usage字段）
        api_key: API密钥
        model: 模型名称
    
    返回:
        (result_json, usage_info) 元组
    """
    if api_key is None:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
    
    client = OpenAI(api_key=api_key, base_url="https://toollearning.cn/v1")
    
    messages = [
        {
            "role": "system",
            "content": "你是一位经验丰富的统计学教师，擅长数据分析方法分类。"
        },
        {
            "role": "user",
            "content": Prompt_question_2 + "\n\n学生的答案内容：\n" + query0_content
        }
    ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)
        
        # 获取token使用信息
        usage_info = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        return result_json, usage_info
    
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"返回内容: {result_text}")
        raise
    except Exception as e:
        print(f"API调用错误: {e}")
        raise


def process_all_query0_files(data_list_dir, api_key=None, model="gpt-4o"):
    """
    处理data_list中所有子文件夹中的query0.json文件
    
    参数:
        data_list_dir: data_list目录路径
        api_key: OpenAI API密钥
        model: 使用的模型
    """
    data_list_path = Path(data_list_dir)
    
    if not data_list_path.exists():
        print(f"目录不存在: {data_list_dir}")
        return
    
    # 获取所有子文件夹
    subfolders = [f for f in data_list_path.iterdir() if f.is_dir()]
    subfolders.sort(key=lambda x: int(x.name))
    
    print(f"找到 {len(subfolders)} 个子文件夹")
    
    success_count = 0
    error_count = 0
    
    for folder in subfolders:
        folder_name = folder.name
        print(f"\n{'=' * 60}")
        print(f"处理文件夹: {folder_name}")
        print(f"{'=' * 60}")
        
        # 查找query0.json文件
        query0_file = folder / "query0.json"
        
        if not query0_file.exists():
            print(f"  跳过: 没有找到query0.json文件")
            error_count += 1
            continue
        
        print(f"  处理文件: {query0_file.name}")
        
        try:
            # 读取query0.json
            with open(query0_file, 'r', encoding='utf-8') as f:
                query0_data = json.load(f)
            
            # 保存token_usage信息
            original_token_usage = query0_data.pop("token_usage", None)
            
            # 将query0内容转换为字符串（不包含token_usage）
            query0_content = json.dumps(query0_data, ensure_ascii=False, indent=2)
            print(f"  内容长度: {len(query0_content)} 字符")
            
            # 调用OpenAI API并获取token使用信息
            result, usage_info = call_openai_api_with_tokens(query0_content, api_key, model)
            
            # 将新的token使用信息添加到结果中
            result["token_usage"] = usage_info
            
            # 保存结果为query1.json
            output_json_path = folder / "query1.json"
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"  结果已保存到: {output_json_path}")
            print(f"  Token使用: {usage_info}")
            success_count += 1
            
        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()
            error_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"处理完成!")
    print(f"成功: {success_count} 个文件")
    print(f"失败: {error_count} 个文件")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    # 设置API密钥
    api_key = "sk-47cMhQHFxQn6MqoYB0800eE0F6F14e878c93Bb0a6337D98e"
    
    # data_list目录路径
    data_list_dir = r"D:\place\study\LLMabstract\data_gen\data_list"
    
    # 处理所有文件夹
    process_all_query0_files(data_list_dir, api_key=api_key, model="gpt-4o-mini")
