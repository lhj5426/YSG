import sys
import re
import os

def calculate_sum_from_txt(file_path):
    """读取 TXT 文件内容并计算每行方括号中的数字总和"""
    total = 0
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                match = re.search(r"\[(\d+)\]", line)
                if match:
                    total += int(match.group(1))
    except Exception as e:
        print(f"处理 TXT 文件 {file_path} 时发生错误：{e}")
    return total

def calculate_sum_from_folder_names(folder_paths):
    """读取文件夹名称中的方括号数字并求和"""
    total = 0
    for folder_path in folder_paths:
        folder_name = os.path.basename(folder_path)  # 获取文件夹名称
        match = re.search(r"\[(\d+)\]", folder_name)
        if match:
            total += int(match.group(1))
        else:
            print(f"文件夹名称 '{folder_name}' 未包含有效的方括号数字，跳过...")
    return total

def main():
    # 检查是否拖拽了文件或文件夹
    if len(sys.argv) < 2:
        print("请将文件夹或 TXT 文件拖拽到此脚本上运行！")
        input("按任意键退出...")
        sys.exit()

    txt_sum = 0
    folder_sum = 0
    folder_paths = []
    txt_paths = []

    # 遍历所有拖拽的路径
    for path in sys.argv[1:]:
        path = path.strip('"')  # 去掉路径中的引号
        if os.path.isfile(path) and path.endswith(".txt"):
            txt_paths.append(path)
        elif os.path.isdir(path):
            folder_paths.append(path)
        else:
            print(f"无效的路径：{path}，跳过...")

    # 处理 TXT 文件
    for txt_file in txt_paths:
        print(f"正在处理 TXT 文件：{txt_file}")
        txt_sum += calculate_sum_from_txt(txt_file)

    # 处理文件夹名称
    if folder_paths:
        print(f"正在处理文件夹：{folder_paths}")
        folder_sum = calculate_sum_from_folder_names(folder_paths)

    # 输出结果
    if txt_paths:
        print(f"所有 TXT 文件中方括号数字的总和为：{txt_sum}")
    if folder_paths:
        print(f"所有文件夹名称中方括号数字的总和为：{folder_sum}")

    # 等待用户按键退出
    input("按任意键退出...")

if __name__ == "__main__":
    main()
