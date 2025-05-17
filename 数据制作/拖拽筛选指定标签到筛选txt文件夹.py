import os
import sys

# ================== 可调参数 ==================
target_class_id = '0'  # 想要筛选的类别 ID，如 '0' 或 '1' 等
output_folder_name = '筛选TXT'  # 输出文件夹名
# ============================================

def filter_txt_files(folder):
    print(f"开始处理文件夹: {folder}")
    output_dir = os.path.join(os.path.dirname(folder), output_folder_name)
    os.makedirs(output_dir, exist_ok=True)

    txt_files = [f for f in os.listdir(folder) if f.lower().endswith('.txt')]

    if not txt_files:
        print("未找到任何 TXT 文件。")
        input("按任意键退出...")
        return

    total_written = 0

    for file_name in txt_files:
        input_path = os.path.join(folder, file_name)
        output_path = os.path.join(output_dir, file_name)

        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        filtered_lines = [line for line in lines if line.strip().startswith(target_class_id + ' ')]

        if filtered_lines:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.writelines(filtered_lines)
            print(f"已写入: {output_path}，共 {len(filtered_lines)} 行")
            total_written += 1
        else:
            print(f"跳过（无匹配行）: {file_name}")

    print(f"\n处理完成，总共生成 {total_written} 个筛选后的 TXT 文件。")
    print(f"输出目录: {output_dir}")
    input("按任意键退出...")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        folder = sys.argv[1]
        if os.path.isdir(folder):
            filter_txt_files(folder)
        else:
            print("错误：请拖入一个文件夹路径。")
            input("按任意键退出...")
    else:
        print("请将包含 TXT 文件的文件夹拖拽到该脚本上。")
        input("按任意键退出...")
