import os
import json
from pathlib import Path
from html_processor import process_html_file
from quality_checker import check_result_quality
from result_modifier import modify_result_with_feedback


def load_data_description():
    """加载数据集描述文件"""
    data_description_path = Path("data_description.json")
    data_description = {}
    if data_description_path.exists():
        with open(data_description_path, 'r', encoding='utf-8') as f:
            data_description = json.load(f)
    return data_description


def process_single_file(html_file, folder, data_description, api_key, model):
    """
    处理单个HTML文件，包含检查-修改循环
    
    参数:
        html_file: HTML文件路径
        folder: 文件夹路径
        data_description: 数据集描述字典
        api_key: API密钥
        model: 模型名称
    
    返回:
        (success, result) 元组
    """
    print(f"  处理HTML文件: {html_file.name}")
    
    try:
        # 获取当前文件夹对应的数据集描述
        folder_name = folder.name
        dataset_desc = None
        if folder_name in data_description:
            # 将数据集描述转换为字符串
            dataset_info = data_description[folder_name]
            dataset_desc = json.dumps(dataset_info, ensure_ascii=False, indent=2)
        
        # 第一步：处理HTML文件，获取初始结果
        result, usage_info, report_content = process_html_file(
            str(html_file), dataset_desc, api_key, model
        )
        
        # 累积token使用信息
        total_usage_info = usage_info.copy()
        
        # 第二步：检查并修改循环（最多5次）
        max_iterations = 1
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
                # 处理feedback可能是列表的情况
                if isinstance(feedback, list):
                    feedback_display = "\n".join([str(item) for item in feedback])[:100]
                else:
                    feedback_display = str(feedback)[:100]
                print(f"    结果不符合原则，修改意见: {feedback_display}...")
                
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
        
        # 将总token使用信息和质量检查信息添加到结果中
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
        
        return True, result
        
    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
        return False, None


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
    data_description = load_data_description()
    
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
            success, _ = process_single_file(
                html_file, folder, data_description, api_key, model
            )
            if success:
                success_count += 1
            else:
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
