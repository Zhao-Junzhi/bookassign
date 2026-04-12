#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试大模型API调用
"""

import json
import logging
from pathlib import Path

# 导入OpenAI库
try:
    import openai
except ImportError:
    import pip
    pip.main(['install', 'openai'])
    import openai

# 导入API配置
try:
    from api_info import api_key, base_url
except ImportError:
    print("错误: 无法导入api_info.py文件，请确保该文件存在且包含api_key和base_url")
    exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_api_call():
    """
    测试API调用
    """
    try:
        # 配置OpenAI客户端
        openai.api_key = api_key
        if base_url:
            openai.api_base = base_url
        
        logger.info(f"开始测试API调用")
        logger.info(f"API URL: {base_url}")
        
        # 构建一个简单的测试请求
        prompt = "请简要介绍一下自己"
        
        # 调用API
        client = openai.AsyncClient(
            api_key=api_key,
            base_url=base_url
        )
        
        import asyncio
        
        async def call_api():
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=60
            )
            return response
        
        response = asyncio.run(call_api())
        
        # 打印结果
        logger.info("API调用成功!")
        logger.info(f"响应内容: {response.choices[0].message.content}")
        
        # 打印token使用量
        if response.usage:
            token_usage = response.usage.to_dict()
            logger.info(f"Token使用量: {token_usage}")
        
        return True
        
    except Exception as e:
        logger.error(f"API调用失败: {e}")
        return False


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("开始测试大模型API调用")
    logger.info("=" * 60)
    
    success = test_api_call()
    
    if success:
        logger.info("API测试成功！")
    else:
        logger.error("API测试失败，请检查配置和网络连接")
    
    logger.info("=" * 60)