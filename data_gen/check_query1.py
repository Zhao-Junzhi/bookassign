from pathlib import Path

data_list_dir = Path(r"D:\place\study\LLMabstract\data_gen\data_list")

# 统计query1.json文件数量
query1_files = list(data_list_dir.rglob("query1.json"))
print(f"生成的query1.json文件数量: {len(query1_files)}")

# 列出前10个
print("\n前10个query1.json文件:")
for i, f in enumerate(query1_files[:10], 1):
    print(f"  {i}. {f.parent.name}/query1.json")

# 统计query0.json文件数量
query0_files = list(data_list_dir.rglob("query0.json"))
print(f"\n存在的query0.json文件数量: {len(query0_files)}")
