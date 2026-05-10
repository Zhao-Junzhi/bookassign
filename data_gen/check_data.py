import pandas as pd
import pickle
import json

with open("data0_processed.json", 'r', encoding='utf-8') as f:
    data1 = json.load(f)

    
def is_subset_dict(dict1, dict2):
    return all(
        key in dict2 and set(value).issubset(set(dict2[key]))
        for key, value in dict1.items()
    )

#检查变量结果是否自洽
for key0 in data1:
    if data1[key0]["input"]["data_description_2"]:
        outputv=data1[key0]["output"]["variable"]
        inputds=data1[key0]["input"]["data_description_2"]
        inputv={key: value.get('变量名', []) 
                for key, value in inputds.items() 
                if value.get('数据类型') == 'DataFrame'}
        
        if is_subset_dict(outputv,inputv)==False:
            print(key0)
    else:
        if data1[key0]["output"]["variable"]!={}:
            print(key0)
            
def dict_structure_equal(dict1, dict2):
    """
    判断两个字典结构是否完全相同
    """
    try:
        # 判断key是否完全相同
        if dict1.keys() != dict2.keys():
            return False
        
        # 判断每个key对应的value是否都是列表且长度相同
        for key in dict1:
            val1, val2 = dict1[key], dict2[key]
            
            # 检查是否都是列表
            if not isinstance(val1, list) or not isinstance(val2, list):
                return False
            
            # 检查列表长度
            if len(val1) != len(val2):
                return False
        
        return True
    
    except (AttributeError, TypeError):
        # 处理输入不是字典的情况
        return False

#检查role的结构是否正确
for key0 in data1:
    if dict_structure_equal(data1[key0]["output"]["variable"], data1[key0]["output"]["role"])!=True:
        print(key0)
        
#检查role的内容是否正确
for key0 in data1:
    for key1 in data1[key0]["output"]["role"]:
        if set(data1[key0]["output"]["role"][key1]).issubset({"dependent","independent","NR","both"})!=True:
            print(key0)
            
    


    
