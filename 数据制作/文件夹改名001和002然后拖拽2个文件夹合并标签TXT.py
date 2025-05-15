import os
import sys

def process_and_save(folder1, folder2, folder3):
    # 如果目标文件夹不存在，则创建
    os.makedirs(folder3, exist_ok=True)

    # 获取文件夹1和文件夹2中的所有TXT文件
    txt_files_1 = [f for f in os.listdir(folder1) if f.endswith('.txt')]
    txt_files_2 = [f for f in os.listdir(folder2) if f.endswith('.txt')]

    all_txt_files = set(txt_files_1 + txt_files_2)  # 合并两个文件夹的文件名集合

    # 合并逻辑
    for index, txt_file in enumerate(all_txt_files, start=1):
        path1 = os.path.join(folder1, txt_file)
        path2 = os.path.join(folder2, txt_file)
        path3 = os.path.join(folder3, txt_file)

        lines_to_write = []

        # 情况 1 和 2: `001` 有内容
        if os.path.exists(path1):
            with open(path1, 'r', encoding='utf-8') as file1:
                lines_to_write.extend(line.strip() for line in file1 if line.strip())

        # 情况 1 和 3: `002` 有内容
        if os.path.exists(path2):
            if os.path.getsize(path2) > 0:
                with open(path2, 'r', encoding='utf-8') as file2:
                    lines_to_write.extend(line.strip() for line in file2 if line.strip())
            else:
                print(f"警告: 文件夹2中的文件 {txt_file} 内容为空，已用文件夹1中的内容替换")

        # 写入合并后的内容到新文件夹3
        with open(path3, 'w', encoding='utf-8') as file3:
            file3.write("\n".join(lines_to_write))
        
        print(f"[{index}/{len(all_txt_files)}] 已处理文件: {txt_file}")

    print("所有文件已处理并保存到新文件夹！")

if __name__ == "__main__":
    # 检查是否拖拽了两个文件夹
    if len(sys.argv) != 3:
        print("请拖拽两个文件夹到脚本上运行！")
        sys.exit(1)

    folder1 = sys.argv[1]
    folder2 = sys.argv[2]
    folder3 = os.path.join(os.path.dirname(folder1), "003")  # 新文件夹路径

    # 确保路径有效且是文件夹
    if not os.path.isdir(folder1) or not os.path.isdir(folder2):
        print("提供的路径不是有效的文件夹，请检查！")
        sys.exit(1)

    print(f"源文件夹: {folder1}")
    print(f"目标文件夹: {folder2}")
    print(f"合并结果将保存到: {folder3}")

    process_and_save(folder1, folder2, folder3)

    # 程序结束提示
    input("处理完成！按任意键退出...")
