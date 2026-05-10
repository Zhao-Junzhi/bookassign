import os
import json
from pathlib import Path
from bs4 import BeautifulSoup
from openai import OpenAI
from prompt import Prompt_question_1, Prompt_question_3


def extract_text_from_html(html_file_path):
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    return text


def call_openai_api_with_tokens(report_content, dataset_description=None, api_key=None, model="gpt-4o"):
    """
    调用OpenAI API并返回结果和token使用信息
    
    参数:
        report_content: HTML报告内容
        dataset_description: 数据集描述
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
    
    # 构建用户内容
    user_content = Prompt_question_1 + "\n\n数据分析报告内容：\n" + report_content
    
    # 添加案例所需数据集情况部分
    if dataset_description:
        user_content += "\n\n案例所需数据集情况：\n" + dataset_description
    else:
        user_content += "\n\n该案例未提供JSON格式的所需数据集情况。"
    
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
    user_content += "\n\n修改意见：\n" + feedback
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


def process_all_folders(data_list_dir, api_key=None, model="gpt-4o"):
    """
    处理data_list中所有子文件夹中的HTML文件
    
    参数:
        data_list_dir: data_list目录路径
        api_key: OpenAI API密钥
        model: 使用的模型
    """
    data_list_path = Path(data_list_dir)
    
    if not data_list_path.exists():
        print(f"目录不存在: {data_list_dir}")
        return
    
    # 读取data_description.json文件
    data_description_path = Path("data_description.json")
    data_description = {}
    if data_description_path.exists():
        with open(data_description_path, 'r', encoding='utf-8') as f:
            data_description = json.load(f)
    
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
        
        # 查找文件夹中的HTML文件
        html_files = list(folder.glob("*.html"))
        
        if not html_files:
            print(f"  跳过: 没有找到HTML文件")
            error_count += 1
            continue
        
        # 处理每个HTML文件
        for html_file in html_files:
            print(f"  处理HTML文件: {html_file.name}")
            
            try:
                # 提取HTML文本
                report_content = extract_text_from_html(str(html_file))
                
                # 获取当前文件夹对应的数据集描述
                folder_name = folder.name
                dataset_desc = None
                if folder_name in data_description:
                    # 将数据集描述转换为字符串
                    dataset_info = data_description[folder_name]
                    dataset_desc = json.dumps(dataset_info, ensure_ascii=False, indent=2)
                
                # 调用OpenAI API并获取token使用信息
                result, usage_info = call_openai_api_with_tokens(report_content, dataset_desc, api_key, model)
                
                # 累积token使用信息
                total_usage_info = usage_info.copy()
                
                # 检查并修改循环（最多5次）
                max_iterations = 5
                iteration = 0
                is_valid = False
                feedback = ""
                
                while iteration < max_iterations:
                    iteration += 1
                    print(f"    第{iteration}次检查结果质量...")
                    
                    # 检查结果质量
                    is_valid, feedback, check_usage = check_result_quality(result, api_key, model)
                    
                    # 累加检查用的token
                    total_usage_info["prompt_tokens"] += check_usage["prompt_tokens"]
                    total_usage_info["completion_tokens"] += check_usage["completion_tokens"]
                    total_usage_info["total_tokens"] += check_usage["total_tokens"]
                    
                    if is_valid:
                        print(f"    结果符合原则，检查通过！")
                        break
                    else:
                        print(f"    结果不符合原则，修改意见: {feedback[:100]}...")
                        
                        if iteration < max_iterations:
                            print(f"    正在根据修改意见修改...")
                            # 根据修改意见修改结果
                            result, modify_usage = modify_result_with_feedback(
                                result, feedback, report_content, dataset_desc, api_key, model
                            )
                            
                            # 累加修改用的token
                            total_usage_info["prompt_tokens"] += modify_usage["prompt_tokens"]
                            total_usage_info["completion_tokens"] += modify_usage["completion_tokens"]
                            total_usage_info["total_tokens"] += modify_usage["total_tokens"]
                        else:
                            print(f"    已达到最大循环次数({max_iterations}次)，使用最后一次结果")
                
                # 将总token使用信息添加到结果中
                result["token_usage"] = total_usage_info
                result["quality_check_iterations"] = iteration
                result["quality_check_passed"] = is_valid
                if not is_valid and feedback:
                    result["final_feedback"] = feedback
                
                # 保存结果为query0.json
                output_json_path = folder / "query0.json"
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                print(f"  结果已保存到: {output_json_path}")
                print(f"  Token使用: {total_usage_info}")
                print(f"  质量检查: {'通过' if is_valid else '未通过'} (迭代{iteration}次)")
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
    process_all_folders(data_list_dir, api_key=api_key, model="gpt-4o-mini")
