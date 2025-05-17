import os
import sys

def process_and_save(folder1, folder2, folder3):
    os.makedirs(folder3, exist_ok=True)

    txt_files_1 = [f for f in os.listdir(folder1) if f.endswith('.txt')]
    txt_files_2 = [f for f in os.listdir(folder2) if f.endswith('.txt')]
    all_txt_files = set(txt_files_1 + txt_files_2)

    total_files = len(all_txt_files)
    print("\n合并过程开始...\n——————————————————————————————")

    for idx, txt_file in enumerate(sorted(all_txt_files), 1):
        path1 = os.path.join(folder1, txt_file)
        path2 = os.path.join(folder2, txt_file)
        path3 = os.path.join(folder3, txt_file)

        lines = []

        if os.path.exists(path1):
            with open(path1, 'r', encoding='utf-8') as f1:
                lines.extend(line.strip() for line in f1 if line.strip())

        if os.path.exists(path2) and os.path.getsize(path2) > 0:
            with open(path2, 'r', encoding='utf-8') as f2:
                lines.extend(line.strip() for line in f2 if line.strip())

        with open(path3, 'w', encoding='utf-8') as f3:
            f3.write('\n'.join(lines))

        print(f"[{idx}/{total_files}] {folder2} 合并进 {folder1} 的文件: {txt_file} （共 {len(lines)} 行）")

    print(f"\n所有文件合并完成，共合并 {total_files} 个文件。")
    print(f"已合并的文件生成在路径：{folder3}")

    print("操作完成，按任意键退出...")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("请将第一个文件夹拖拽到此脚本上启动。")
        input("按任意键退出...")
        sys.exit(1)

    folder1 = sys.argv[1]
    print(f"第一个文件夹已接收：{folder1}")

    folder2 = input("请拖拽第二个文件夹到此窗口后按回车确认：").strip()

    if not os.path.isdir(folder1):
        print(f"第一个路径不是有效文件夹：{folder1}")
        input("按任意键退出...")
        sys.exit(1)

    if not os.path.isdir(folder2):
        print(f"第二个路径不是有效文件夹：{folder2}")
        input("按任意键退出...")
        sys.exit(1)

    print(f"第二个文件夹已接收：{folder2}")
    input("如要开始合并请按回车...")

    folder3 = os.path.join(os.path.dirname(folder1), "003")
    print(f"合并输出路径：{folder3}")

    process_and_save(folder1, folder2, folder3)

    input()
