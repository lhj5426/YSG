import os
import json

def process_json_file(json_path):
    """
    处理单个JSON文件，根据规则修改标签。
    """
    print(f"--- 正在处理文件: {os.path.basename(json_path)} ---")

    # 定义需要交替修改的标签
    target_labels = {"qipao", "balloon", "changfangtiao"}
    
    # 为每个目标标签创建一个独立的计数器
    counters = {label: 0 for label in target_labels}

    try:
        # 使用 'utf-8' 编码读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"错误：无法读取或解析JSON文件 {json_path}。原因: {e}")
        return

    # 检查JSON数据结构，通常标注信息在 'shapes' 键下
    if 'shapes' not in data or not isinstance(data['shapes'], list):
        print(f"警告：在 {json_path} 中未找到 'shapes' 列表，跳过此文件。")
        return

    # 遍历所有标注对象
    for shape in data['shapes']:
        label = shape.get('label')

        # 如果标签是我们关注的目标之一
        if label in target_labels:
            # 对应标签的计数器加 1
            counters[label] += 1
            
            # 如果计数器是偶数 (第二个, 第四个, ...)，则修改标签
            if counters[label] % 2 == 0:
                new_label = f"{label}2"
                shape['label'] = new_label
                print(f"  已将第 {counters[label]} 个 '{label}' 修改为 '{new_label}'")

    # 将修改后的内容写回原文件
    try:
        # 使用 'utf-8' 编码和缩进写回JSON文件，确保可读性
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"--- 文件 {os.path.basename(json_path)} 处理完成并已保存。 ---\n")
    except Exception as e:
        print(f"错误：无法写入文件 {json_path}。原因: {e}")

def main():
    """
    主函数，查找与图片同名的JSON文件并进行处理。
    """
    # 获取脚本所在的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"脚本正在以下目录中运行: {script_dir}\n")

    # 定义常见的图片文件扩展名
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
    
    found_files = False
    # 遍历目录中的所有文件
    for filename in os.listdir(script_dir):
        # 分离文件名和扩展名
        base_name, extension = os.path.splitext(filename)
        
        # 检查是否是图片文件
        if extension.lower() in image_extensions:
            # 构建对应的JSON文件名
            json_filename = base_name + '.json'
            json_path = os.path.join(script_dir, json_filename)
            
            # 检查同名的JSON文件是否存在
            if os.path.exists(json_path):
                found_files = True
                process_json_file(json_path)
            else:
                print(f"未找到与图片 '{filename}' 对应的JSON文件 '{json_filename}'，已跳过。\n")

    if not found_files:
        print("未在当前目录中找到任何匹配的图片和JSON文件对。")

    # 在程序结束时等待用户按键，以便查看输出信息
    input("\n所有操作已完成。按 Enter 键退出...")

if __name__ == "__main__":
    main()