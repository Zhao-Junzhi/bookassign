import pickle
import pandas as pd
import os
import json
import numpy as np
from pathlib import Path


def convert_to_serializable(obj):
    """
    将对象转换为JSON可序列化的格式
    """
    if isinstance(obj, (np.integer, np.floating)):
        if np.isnan(obj):
            return None
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    elif pd.isna(obj):
        return None
    return obj


def analyze_pkl_file(file_path):
    """
    分析pkl文件并返回基本信息字典
    
    参数:
        file_path: pkl文件路径
    
    返回:
        包含分析结果的字典
    """
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return None
    
    result = {}
    
    try:
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        
        # 数据类型
        result['数据类型'] = type(data).__name__
        
        if isinstance(data, pd.DataFrame):
            # DataFrame处理
            result['数据形状'] = f"{data.shape[0]} 行 × {data.shape[1]} 列"
            
            # 变量名
            result['变量名'] = list(data.columns)
            
            # 数据类型统计（转换为字符串）
            dtypes_dict = {}
            for col, dtype in data.dtypes.items():
                dtypes_dict[col] = str(dtype)
            result['数据类型统计'] = dtypes_dict
            
            # 前5行示例
            result['前5行示例'] = data.head().to_dict()
            
            # 基本统计信息
            result['基本统计信息'] = data.describe().to_dict()
            
            # 缺失值统计
            result['缺失值统计'] = data.isnull().sum().to_dict()
        
        elif isinstance(data, dict):
            # 字典处理
            result['数据形状'] = f"字典长度: {len(data)}"
            result['变量名'] = list(data.keys())
            
            if data:
                result['前5行示例'] = dict(list(data.items())[:5])
        
        elif isinstance(data, list):
            # 列表处理
            result['数据形状'] = f"列表长度: {len(data)}"
            if data:
                result['前5行示例'] = data[:5]
        
        elif hasattr(data, '__len__'):
            # 其他可迭代对象
            result['数据形状'] = f"长度: {len(data)}"
            if len(data) > 0:
                result['前5行示例'] = list(data)[:5]
        
        return result
        
    except Exception as e:
        print(f"分析错误: {str(e)}")
        return None


def get_subdirectories_pathlib(directory):
    """获取目录下所有子目录的绝对路径，按文件夹名称（数字）排序"""
    path = Path(directory).resolve()
    
    # 获取所有子目录
    subdirs = [p for p in path.iterdir() if p.is_dir()]
    
    # 按文件夹名称（数字）排序
    subdirs.sort(key=lambda x: int(x.name))
    
    # 转换为绝对路径
    subdirs = [str(p.resolve()) for p in subdirs]
    
    return subdirs


def get_pkl_files_pathlib(directory):
    """获取目录下所有pkl文件的绝对路径"""
    path = Path(directory).resolve()  # resolve() 获取绝对路径
    
    # 递归查找所有.pkl文件
    pkl_files = [str(p.resolve()) for p in path.rglob("*.pkl") if p.is_file()]
    
    return pkl_files


if __name__ == "__main__":
    import pickle
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(script_dir, "data_list")
    
    files = get_subdirectories_pathlib(directory)
    
    all_results = {}

    for a, file in enumerate(files):
        files_to_analyze = get_pkl_files_pathlib(file)
        if files_to_analyze:
            # 确保文件夹ID键存在
            folder_id = str(a + 1)
            if folder_id not in all_results:
                all_results[folder_id] = {}
            
            for file_path in files_to_analyze:
                print(f"\n{'=' * 60}")
                print(f"分析文件: {file_path}")
                print(f"{'=' * 60}")
                
                result = analyze_pkl_file(file_path)
                
                if result:
                    # 使用文件名作为key
                    filename = os.path.basename(file_path)
                    all_results[folder_id][filename] = result
                    
                    # 打印结果
                    print("\n分析结果:")
                    for key, value in result.items():
                        print(f"\n{key}:")
                        if isinstance(value, dict):
                            for k, v in value.items():
                                print(f"  {k}: {v}")
                        elif isinstance(value, list):
                            for i, item in enumerate(value, 1):
                                print(f"  {i}. {item}")
                        else:
                            print(f"  {value}")
    
    # 保存为pickle文件
    with open('results.pkl', 'wb') as f:
        pickle.dump(all_results, f)
