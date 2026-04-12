import glob
import json
import re
import os

def extract_first_int(text):
    match = re.search(r'\d+', text)
    return match.group() if match else None

def get_json_files_relative(subdir):
    """
    获取指定子目录下所有 JSON 文件的相对路径
    
    Args:
        subdir: 子目录名称，如 'data'
    
    Returns:
        list: 相对路径列表
    """
    pattern = os.path.join(subdir, '**', '*.json')
    json_files = glob.glob(pattern, recursive=True)
    return json_files

# 使用示例
json_files = get_json_files_relative('book4_r1')
this_dic={}
num=0

for file_path in json_files:
    print(f"读取文件: {file_path}")
    key0 = file_path
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 创建基础ip字典（不会被内层循环修改的部分）
    base_ip = {
        "background": data["background"],
        "data": data["data"]
    }

    for qs in data["task"]:
        num += 1
        
        # 为每个问题创建新的字典副本
        this_dic[str(num)] = {
            "case_id": key0,
            "input": {
                **base_ip,  # 复制基础ip
                "question": qs["query"]  # 添加问题特定的字段
            },
            "output": {
                "answer": qs["answer"]
            },
            "meta_info":data["meta_info"]
        }

with open('data0_book4.json', 'w', encoding='utf-8') as f:
    json.dump(this_dic, f, ensure_ascii=False, indent=2)

import pickle

with open('data0_book4.pkl', 'wb') as f:  # 'wb'表示以二进制写入模式
    pickle.dump(this_dic, f)
