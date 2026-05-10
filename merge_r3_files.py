#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并当前路径中所有r3结尾目录下的JSON文件，key从"1"（字符串）开始编排
分别导出JSON和pkl文件
"""

import os
import json
import pickle
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def merge_r3_files():
    """
    合并所有r3结尾目录下的JSON文件
    """
    base_dir = Path(r'd:\place\study\bookassign')
    
    # 找到所有以r3结尾的目录
    r3_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name.endswith('r3')]
    
    if not r3_dirs:
        logger.warning("没有找到以r3结尾的目录")
        return
    
    # 收集所有JSON文件
    json_files = []
    for r3_dir in r3_dirs:
        files = list(r3_dir.glob('*.json'))
        json_files.extend(files)
        logger.info(f"从 {r3_dir.name} 目录收集了 {len(files)} 个JSON文件")
    
    total_files = len(json_files)
    logger.info(f"总共收集了 {total_files} 个JSON文件")
    
    if total_files == 0:
        logger.warning("没有找到JSON文件")
        return
    
    # 合并文件
    merged_data = {}
    for i, json_file in enumerate(json_files, 1):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 使用字符串类型的key
            key = str(i)
            merged_data[key] = data
            
            if i % 100 == 0 or i == total_files:
                logger.info(f"已处理 {i}/{total_files} 个文件")
                
        except Exception as e:
            logger.error(f"处理文件 {json_file.name} 时出错: {e}")
    
    # 导出为JSON文件
    json_output = base_dir / 'merged_r3_files.json'
    try:
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        logger.info(f"已导出为JSON文件: {json_output}")
    except Exception as e:
        logger.error(f"导出JSON文件失败: {e}")
    
    # 导出为pkl文件
    pkl_output = base_dir / 'merged_r3_files.pkl'
    try:
        with open(pkl_output, 'wb') as f:
            pickle.dump(merged_data, f)
        logger.info(f"已导出为pkl文件: {pkl_output}")
    except Exception as e:
        logger.error(f"导出pkl文件失败: {e}")
    
    logger.info(f"合并完成，共处理了 {len(merged_data)} 个文件")


if __name__ == '__main__':
    logger.info("开始合并r3目录下的JSON文件...")
    merge_r3_files()
    logger.info("合并完成！")