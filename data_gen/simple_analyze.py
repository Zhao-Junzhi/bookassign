import pickle
import os

# 简单版本：只读取文件并显示基本信息
def simple_analyze_pkl(file_path):
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print(f"分析文件: {os.path.basename(file_path)}")
    print("=" * 80)
    
    try:
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"数据类型: {type(data).__name__}")
        
        # 尝试使用pandas（如果可用）
        try:
            import pandas as pd
            
            if isinstance(data, pd.DataFrame):
                print(f"数据形状: {data.shape[0]} 行 × {data.shape[1]} 列")
                print(f"\n变量名:")
                for i, col in enumerate(data.columns, 1):
                    print(f"  {i}. {col}")
                
                print(f"\n前3行示例:")
                print(data.head(3))
                
            else:
                print(f"数据不是DataFrame类型")
                print(f"尝试转换为DataFrame...")
                df = pd.DataFrame(data)
                print(f"转换后形状: {df.shape}")
                print(f"前3行:")
                print(df.head(3))
                
        except Exception as e:
            print(f"pandas操作失败: {e}")
            print(f"基本信息:")
            print(f"类型: {type(data)}")
            if hasattr(data, '__len__'):
                print(f"长度: {len(data)}")
            if hasattr(data, 'keys'):
                print(f"键: {list(data.keys())[:5]}")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"分析错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 获取脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 直接指定要分析的文件路径（使用绝对路径）
    files_to_analyze = [
        os.path.join(script_dir, 'data', 'country.pkl'),
        os.path.join(script_dir, 'data', 'gggr.pkl')
    ]
    
    for file_path in files_to_analyze:
        print(f"\n{'=' * 60}")
        print(f"分析文件: {file_path}")
        print(f"{'=' * 60}")
        simple_analyze_pkl(file_path)
