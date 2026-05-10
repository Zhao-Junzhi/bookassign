import os
import jieba
from pathlib import Path


def load_stopwords():
    """
    加载常见的中文停用词
    """
    # 常见中文停用词列表
    stopwords = set([
        '的', '了', '和', '是', '就', '都', '而', '及', '与', '着', '或', '一个', '没有', '我们', '你们', '他们',
        '这', '那', '这些', '那些', '这样', '那样', '这里', '那里', '因为', '所以', '如果', '虽然', '但是',
        '然而', '因此', '于是', '不过', '只是', '已经', '现在', '过去', '将来', '可以', '能够', '应该', '必须',
        '可能', '也许', '大概', '大约', '非常', '特别', '很', '太', '比较', '最', '更', '越', '最', '还', '也',
        '又', '再', '并', '就', '却', '可', '才', '要', '会', '能', '想', '看', '说', '做', '认为', '觉得', '感觉',
        '知道', '了解', '学习', '研究', '分析', '讨论', '问题', '方法', '结果', '结论', '数据', '信息', '模型',
        '系统', '工具', '技术', '方法', '过程', '步骤', '阶段', '时期', '时间', '空间', '范围', '领域', '方面',
        '角度', '层面', '层次', '维度', '因素', '变量', '指标', '参数', '特征', '属性', '性质', '特点', '特征',
        '功能', '作用', '影响', '效果', '意义', '价值', '重要性', '必要性', '可能性', '可行性', '实用性', '有效性',
        '准确性', '可靠性', '稳定性', '安全性', '效率', '质量', '水平', '程度', '规模', '范围', '数量', '程度',
        '大小', '多少', '高低', '深浅', '远近', '快慢', '好坏', '优劣', '真假', '对错', '是非', '善恶', '美丑',
        '成败', '得失', '利弊', '祸福', '好坏', '优劣', '真假', '对错', '是非', '善恶', '美丑', '成败', '得失',
        '利弊', '祸福', '好坏', '优劣', '真假', '对错', '是非', '善恶', '美丑', '成败', '得失', '利弊', '祸福'
    ])
    return stopwords


def process_text_without_stopwords(text, stopwords):
    """
    分词并去除停用词
    """
    # 使用jieba分词
    words = jieba.cut(text)
    # 去除停用词
    filtered_words = [word for word in words if word not in stopwords and len(word) > 1]
    return ' '.join(filtered_words)


def main():
    # 文本文件路径
    text_file = r"D:\place\study\LLMabstract\data\data_list\chinese_text.txt"
    
    if not os.path.exists(text_file):
        print(f"文件不存在: {text_file}")
        return
    
    # 读取文本
    with open(text_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"原始文本长度: {len(text)}")
    
    # 加载停用词
    stopwords = load_stopwords()
    
    # 处理文本（分词并去除停用词）
    processed_text = process_text_without_stopwords(text, stopwords)
    
    print(f"处理后文本长度: {len(processed_text)}")
    
    # 保存处理后的文本
    output_text = r"D:\place\study\LLMabstract\data\data_list\processed_text.txt"
    with open(output_text, 'w', encoding='utf-8') as f:
        f.write(processed_text)
    
    print(f"处理后的文本已保存到: {output_text}")
    
    # 尝试生成词云
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
        
        # 创建词云
        wc = WordCloud(
            font_path='C:\\Windows\\Fonts\\simhei.ttf',  # 中文字体
            width=1200,
            height=800,
            background_color='white',
            max_words=2000,
            max_font_size=100,
            random_state=42
        )
        
        # 生成词云
        wc.generate(processed_text)
        
        # 保存词云图
        output_image = r"D:\place\study\LLMabstract\data\data_list\wordcloud.png"
        plt.figure(figsize=(12, 8))
        plt.imshow(wc, interpolation='bilinear')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_image, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"词云图已保存到: {output_image}")
        
    except ImportError:
        print("wordcloud模块未安装，无法生成词云图")
        print("请使用以下命令安装：pip install wordcloud")
    except Exception as e:
        print(f"生成词云图时出错: {e}")


if __name__ == "__main__":
    main()
