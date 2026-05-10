import pickle
import json

# 读取pickle文件
with open('results.pkl', 'rb') as f:
    results = pickle.load(f)
    
print(results["9"])
    
class StringEncoder(json.JSONEncoder):
    def default(self, obj):
        # 将所有非基本类型转换为字符串
        return str(obj)
    
with open('results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, cls=StringEncoder, ensure_ascii=False, indent=4)