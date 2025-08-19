import os
import json

def revert_json_file(json_path):
    """
    处理单个JSON文件，将带 '2' 的标签还原。
    """
    print(f"--- 正在还原文件: {os.path.basename(json_path)} ---")

    # 定义需要还原的标签映射关系
    # 键是需要被替换的标签，值是替换后的新标签
    labels_to_revert = {
        "qipao2": "qipao",
        "balloon2": "balloon",
        "changfangtiao2": "changfangtiao"
    }
    
    try:
        # 使用 'utf-8' 编码读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"错误：无法读取或解析JSON文件 {json_path}。原因: {e}")
        return

    # 检查JSON数据结构
    if 'shapes' not in data or not isinstance(data['shapes'], list):
        print(f"警告：在 {json_path} 中未找到 'shapes' 列表，跳过此文件。")
        return

    # 遍历所有标注对象
    for shape in data['shapes']:
        label = shape.get('label')

        # 如果当前标签是我们需要还原的标签之一
        if label in labels_to_revert:
            # 获取还原后的新标签
            original_label = labels_to_revert[label]
            # 更新标签
            shape['label'] = original_label
            print(f"  已将 '{label}' 还原为 '{original_label}'")

    # 将修改后的内容写回原文件
    try:
        # 使用 'utf-8' 编码和缩进写回JSON文件
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"--- 文件 {os.path.basename(json_path)} 还原完成并已保存。 ---\n")
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
                revert_json_file(json_path)
            else:
                print(f"未找到与图片 '{filename}' 对应的JSON文件 '{json_filename}'，已跳过。\n")

    if not found_files:
        print("未在当前目录中找到任何匹配的图片和JSON文件对。")

    # 在程序结束时等待用户按键
    input("\n所有标签已还原。按 Enter 键退出...")

if __name__ == "__main__":
    main()