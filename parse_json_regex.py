#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用正则表达式解析类JSON文件
处理转义字符不规范、引号使用不一致等格式问题
"""

import re
from pathlib import Path
from typing import Dict, Optional


def parse_json_like_file(file_path: Path) -> Optional[Dict]:
    """
    使用正则表达式解析类JSON文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        解析后的字典，失败返回None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除BOM标记
        if content.startswith('\ufeff'):
            content = content[1:]
        
        # 使用正则表达式提取字段
        result = {}
        
        # 提取 id 字段
        id_match = re.search(r'"id"\s*:\s*"([^"]*)"', content)
        if id_match:
            result['id'] = id_match.group(1)
        
        # 提取 question 字段（可能包含换行）
        question_match = re.search(r'"question"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
        if question_match:
            result['question'] = question_match.group(1)
        
        # 提取 data 字段（可能包含复杂的LaTeX代码和换行）
        data_match = re.search(r'"data"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
        if data_match:
            # 处理转义字符
            data_content = data_match.group(1)
            # 将 \\n 转换为实际换行符
            data_content = data_content.replace('\\n', '\n')
            # 将 \\t 转换为制表符
            data_content = data_content.replace('\\t', '\t')
            # 将 \\r 转换为回车符
            data_content = data_content.replace('\\r', '\r')
            # 将 \\" 转换为引号
            data_content = data_content.replace('\\"', '"')
            # 将 \\\\ 转换为反斜杠
            data_content = data_content.replace('\\\\', '\\')
            result['data'] = data_content
        
        # 提取 answer 字段
        answer_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
        if answer_match:
            answer_content = answer_match.group(1)
            # 处理转义字符
            answer_content = answer_content.replace('\\n', '\n')
            answer_content = answer_content.replace('\\t', '\t')
            answer_content = answer_content.replace('\\"', '"')
            answer_content = answer_content.replace('\\\\', '\\')
            result['answer'] = answer_content
        
        # 提取 meta info 字段（嵌套对象）
        meta_match = re.search(r'"meta info"\s*:\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', content, re.DOTALL)
        if meta_match:
            meta_content = meta_match.group(0)
            # 解析meta info中的各个字段
            meta_info = {}
            
            # 提取 index
            index_match = re.search(r'"index"\s*:\s*"([^"]*)"', meta_content)
            if index_match:
                meta_info['index'] = index_match.group(1)
            
            # 提取 image
            image_match = re.search(r'"image"\s*:\s*"([^"]*)"', meta_content)
            if image_match:
                meta_info['image'] = image_match.group(1)
            
            # 提取 caption
            caption_match = re.search(r'"caption"\s*:\s*"([^"]*)"', meta_content)
            if caption_match:
                meta_info['caption'] = caption_match.group(1)
            
            # 提取 chapter
            chapter_match = re.search(r'"chapter"\s*:\s*"([^"]*)"', meta_content)
            if chapter_match:
                meta_info['chapter'] = chapter_match.group(1)
            
            # 提取 section
            section_match = re.search(r'"section"\s*:\s*"([^"]*)"', meta_content)
            if section_match:
                meta_info['section'] = section_match.group(1)
            
            # 提取 page
            page_match = re.search(r'"page"\s*:\s*"([^"]*)"', meta_content)
            if page_match:
                meta_info['page'] = page_match.group(1)
            
            result['meta info'] = meta_info
        
        return result
        
    except Exception as e:
        print(f"解析文件 {file_path.name} 时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_parse_file(file_path: Path):
    """测试解析单个文件"""
    print(f"\n解析文件: {file_path.name}")
    print("=" * 60)
    
    result = parse_json_like_file(file_path)
    
    if result:
        print("解析成功!")
        print(f"ID: {result.get('id', 'N/A')}")
        print(f"Question: {result.get('question', 'N/A')[:80]}...")
        print(f"Answer: {result.get('answer', 'N/A')[:80]}...")
        print(f"Data长度: {len(result.get('data', ''))} 字符")
        print(f"Meta info keys: {list(result.get('meta info', {}).keys())}")
        
        # 显示data字段的前100字符
        data = result.get('data', '')
        print(f"\nData字段前100字符:")
        print(repr(data[:100]))
    else:
        print("解析失败!")


if __name__ == "__main__":
    # 测试解析record_001.json
    test_file = Path(r'd:\place\study\bookassign\book1\record_001.json')
    test_parse_file(test_file)
