import os
import sys

def modify_first_number_in_line(line, target_number, new_number, replaced_lines):
    """将一行的第一个数字修改为指定的数字（如果该数字等于目标数字）"""
    parts = line.split()
    if parts:
        try:
            first_number = float(parts[0])  # 获取该行的第一个数字
            if first_number == target_number:  # 如果该数字等于目标数字
                replaced_lines.append(f"已将 {first_number} 替换为 {new_number}：{line.strip()}")
                parts[0] = str(new_number)  # 如果该数字等于目标数字，则替换
        except ValueError:
            pass  # 如果第一部分不是数字，则跳过这一行
    return ' '.join(parts)

def process_txt_file(file_path, target_number, new_number, replaced_lines):
    """修改文件中的每一行的开头数字（只替换符合条件的行）"""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    modified_lines = []
    for line in lines:
        # 跳过空行
        if line.strip():  # 如果不是空行
            modified_lines.append(modify_first_number_in_line(line, target_number, new_number, replaced_lines))

    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines('\n'.join(modified_lines) + '\n')

    print(f'处理完成: {file_path}')

def process_directory(directory, target_number, new_number, replaced_lines):
    """处理目录下的所有 TXT 文件"""
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.txt'):
                file_path = os.path.join(root, filename)
                process_txt_file(file_path, target_number, new_number, replaced_lines)

def main():
    target_number = 1  # 你希望替换的目标类别（0 balloon 1 qipao 2 fangkuai 3 changfangtiao 4 kuangwai）
    new_number = 0     # 你希望替换成的新类别（0 balloon 1 qipao 2 fangkuai 3 changfangtiao 4 kuangwai）
    replaced_lines = []  # 用来记录哪些行被修改

    if len(sys.argv) > 1:
        # 处理拖拽的文件或文件夹
        for path in sys.argv[1:]:
            if os.path.isfile(path) and path.endswith('.txt'):
                process_txt_file(path, target_number, new_number, replaced_lines)
            elif os.path.isdir(path):
                process_directory(path, target_number, new_number, replaced_lines)
    else:
        # 双击运行，遍历当前目录下所有 TXT 文件
        script_dir = os.path.dirname(os.path.realpath(__file__))
        process_directory(script_dir, target_number, new_number, replaced_lines)

    print('所有文件处理完成。')

    # 打印所有替换记录
    if replaced_lines:
        print("\n--- 替换记录 ---")
        for line in replaced_lines:
            print(line)
    else:
        print("没有进行任何替换。")

    # 等待用户按任意键继续
    input("\n按任意键继续...")

if __name__ == '__main__':
    main()
