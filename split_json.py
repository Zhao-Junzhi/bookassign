#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将data0_book12345.json中的每个条目保存为单独的JSON文件
"""

import json
import os
from pathlib import Path

# 配置参数
INPUT_FILE = Path(r'd:\place\study\bookassign\data0_book4.json')
OUTPUT_DIR = Path(r'd:\place\study\bookassign\book4_r2')

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def split_json():
    """
    将JSON文件中的每个条目保存为单独的文件
    """
    try:
        # 读取输入文件
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 遍历每个条目
        for key, value in data.items():
            # 添加sample_key字段
            value['sample_key'] = key
            
            # 构建输出文件路径
            output_file = OUTPUT_DIR / f"{key}.json"
            
            # 保存为单独的JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
            
            print(f"已保存: {output_file.name}")
        
        print(f"\n处理完成！共保存了 {len(data)} 个文件")
        
    except Exception as e:
        print(f"处理过程中出错: {e}")

if __name__ == '__main__':
    split_json()
