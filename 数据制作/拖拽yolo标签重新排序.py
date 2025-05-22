import os
import sys
from collections import defaultdict

def sort_txt_by_label_id(lines):
    lines = [line for line in lines if line.strip()]
    label_groups = defaultdict(list)

    for line in lines:
        parts = line.strip().split()
        if parts:
            label_id = int(parts[0])
            label_groups[label_id].append(line.strip())

    sorted_labels = sorted(label_groups.keys())

    print("排序过程：")
    for label in sorted_labels:
        count = len(label_groups[label])
        print(f"  标签 {label}：{count} 行")

    # 将分组内容按标签 ID 顺序拼接
    sorted_lines = []
    for label in sorted_labels:
        sorted_lines.extend(label_groups[label])

    return sorted_lines

def process_folder(folder_path):
    output_folder = os.path.join(os.path.dirname(folder_path), 'YOLO标签重新排序')
    os.makedirs(output_folder, exist_ok=True)

    txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    if not txt_files:
        print("文件夹中没有 TXT 文件。")
        return

    for txt_file in txt_files:
        input_path = os.path.join(folder_path, txt_file)
        output_path = os.path.join(output_folder, txt_file)

        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        print(f"\n正在处理文件：{txt_file}")
        print("-" * 40)
        sorted_lines = sort_txt_by_label_id(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            for line in sorted_lines:
                f.write(line + '\n')

        print("排序完成，已写入新文件夹。")

    print(f"\n共处理 {len(txt_files)} 个 TXT 文件")
    print(f"排序结果保存在：{output_folder}")
    input("\n请按任意键退出...")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("请将包含 YOLO 标签的文件夹拖到此脚本上运行。")
        input("按任意键退出...")
        sys.exit()

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print("拖入的不是文件夹。")
        input("按任意键退出...")
        sys.exit()

    process_folder(folder)
