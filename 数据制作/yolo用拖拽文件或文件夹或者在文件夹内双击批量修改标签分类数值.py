import os
import sys

def modify_first_number_in_line(line, new_number):
    """将一行的第一个数字修改为指定的数字"""
    parts = line.split()
    if parts:
        parts[0] = str(new_number)
    return ' '.join(parts)

def process_txt_file(file_path, new_number):
    """修改文件中的每一行的开头数字"""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    modified_lines = [modify_first_number_in_line(line, new_number) for line in lines]

    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines('\n'.join(modified_lines) + '\n')

    print(f'Processed: {file_path}')

def process_directory(directory, new_number):
    """处理目录下的所有 TXT 文件"""
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.txt'):
                file_path = os.path.join(root, filename)
                process_txt_file(file_path, new_number)

def main():
    new_number = 2  # 你希望设置的数字

    if len(sys.argv) > 1:
        # 处理拖拽的文件或文件夹
        for path in sys.argv[1:]:
            if os.path.isfile(path) and path.endswith('.txt'):
                process_txt_file(path, new_number)
            elif os.path.isdir(path):
                process_directory(path, new_number)
    else:
        # 双击运行，遍历当前目录下所有 TXT 文件
        script_dir = os.path.dirname(os.path.realpath(__file__))
        process_directory(script_dir, new_number)

    print('All files processed.')

if __name__ == '__main__':
    main()
