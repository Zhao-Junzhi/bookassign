import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import jieba


def extract_chinese_text(html_content):
    """
    从HTML内容中提取中文文本
    """
    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    # 提取纯文本
    text = soup.get_text(separator='\n', strip=True)
    # 只保留中文字符
    chinese_text = ''.join(re.findall(r'[\u4e00-\u9fa5]+', text))
    return chinese_text


def process_all_html_files(data_list_dir):
    """
    处理所有子文件夹中的HTML文件，提取中文文本
    """
    data_list_path = Path(data_list_dir)
    
    if not data_list_path.exists():
        print(f"目录不存在: {data_list_dir}")
        return ""
    
    # 获取所有子文件夹
    subfolders = [f for f in data_list_path.iterdir() if f.is_dir()]
    subfolders.sort(key=lambda x: int(x.name))
    
    print(f"找到 {len(subfolders)} 个子文件夹")
    
    all_chinese_text = ""
    
    for folder in subfolders:
        folder_name = folder.name
        print(f"\n处理文件夹: {folder_name}")
        
        # 查找HTML文件
        html_files = list(folder.glob("*.html"))
        
        if not html_files:
            print(f"  跳过: 没有找到HTML文件")
            continue
        
        for html_file in html_files:
            print(f"  处理文件: {html_file.name}")
            
            try:
                # 读取HTML文件
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 提取中文文本
                chinese_text = extract_chinese_text(html_content)
                all_chinese_text += chinese_text + " "
                
                print(f"  提取中文文本长度: {len(chinese_text)}")
                
            except Exception as e:
                print(f"  错误: {e}")
    
    print(f"\n总中文文本长度: {len(all_chinese_text)}")
    return all_chinese_text


def generate_wordcloud(text, output_path):
    """
    生成词云图并保存
    """
    if not text:
        print("没有文本数据，无法生成词云")
        return False
    
    # 使用jieba分词
    words = jieba.cut(text)
    word_list = ' '.join(words)
    
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
    wc.generate(word_list)
    
    # 保存词云图
    plt.figure(figsize=(12, 8))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"词云图已保存到: {output_path}")
    return True


if __name__ == "__main__":
    # data_list目录路径
    data_list_dir = r"D:\place\study\LLMabstract\data\data_list"
    
    # 处理所有HTML文件，提取中文文本
    chinese_text = process_all_html_files(data_list_dir)
    
    # 生成词云图
    output_path = os.path.join(data_list_dir, "wordcloud.png")
    generate_wordcloud(chinese_text, output_path)
