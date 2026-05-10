import json

with open('analysis_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'总文件夹数: {len(data)}')
print(f'文件夹ID列表: {sorted(data.keys())}')

# 统计每个文件夹中的pkl文件数量
print('\n每个文件夹中的pkl文件数量:')
for folder_id in sorted(data.keys()):
    file_count = len(data[folder_id])
    print(f'  文件夹 {folder_id}: {file_count} 个pkl文件')
