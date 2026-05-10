import csv
import json
import pickle
import os

# 文件路径
csv_path = r"D:\place\study\LLMabstract\data_gen\data0_processed.csv"
json_path = r"D:\place\study\LLMabstract\data_gen\data0_processed.json"
pkl_path = r"D:\place\study\LLMabstract\data_gen\data0_processed.pkl"

# 读取CSV文件并构建数据结构
data = {}

with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # 提取数据
        key = row['key']
        case_id = row['case_id']
        
        # 解析input字段
        try:
            input_data = json.loads(row['input'])
        except Exception as e:
            print(f"解析input失败 for key {key}: {e}")
            input_data = {}
        
        # 解析output字段
        try:
            output_data = json.loads(row['output'])
        except Exception as e:
            print(f"解析output失败 for key {key}: {e}")
            # 尝试处理可能的格式问题
            output_str = row['output']
            # 移除首尾的引号
            if output_str.startswith('"') and output_str.endswith('"'):
                output_str = output_str[1:-1]
            # 替换转义的引号
            output_str = output_str.replace('\\"', '"')
            try:
                output_data = json.loads(output_str)
                print(f"重新解析成功 for key {key}")
            except:
                output_data = {}
                print(f"无法解析output for key {key}")
        
        # 构建样本
        sample = {
            'case_id': case_id,
            'input': input_data,
            'output': output_data
        }
        
        # 添加到数据结构
        data[key] = sample

# 按key的数字顺序排序
sorted_data = dict(sorted(data.items(), key=lambda x: int(x[0])))

# 保存为JSON文件
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(sorted_data, f, ensure_ascii=False, indent=2)

print(f"成功更新JSON文件: {json_path}")

# 保存为PKL文件
with open(pkl_path, 'wb') as f:
    pickle.dump(sorted_data, f)

print(f"成功更新PKL文件: {pkl_path}")
print("更新完成!")
