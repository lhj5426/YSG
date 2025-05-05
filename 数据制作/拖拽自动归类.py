import os
import sys
import shutil

# ================== Adjustable Parameters ==================
move_files_instead_of_copy = True  # True = 移动文件；False = 拷贝文件
enable_recursive = False            # True = 递归处理子文件夹；False = 只处理当前目录
# ===========================================================

def classify_files(folder):
    print(f"开始整理文件夹: {folder}")
    file_op = shutil.move if move_files_instead_of_copy else shutil.copy

    # 根据是否递归决定遍历方式
    if enable_recursive:
        print("启用递归模式，处理所有子目录文件...")
        all_files = []
        for root, _, files in os.walk(folder):
            for f in files:
                all_files.append(os.path.join(root, f))
    else:
        print("仅处理当前文件夹中的文件...")
        all_files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

    if not all_files:
        print("没有找到任何文件。")
        input("按任意键退出...")
        return

    for file_path in all_files:
        if not os.path.isfile(file_path):
            continue

        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower().lstrip('.')
        ext_folder = ext.upper() if ext else 'NO_EXT'

        dest_dir = os.path.join(folder, ext_folder)
        os.makedirs(dest_dir, exist_ok=True)

        dest_path = os.path.join(dest_dir, filename)

        # 避免源路径和目标路径相同导致错误
        if os.path.abspath(file_path) == os.path.abspath(dest_path):
            continue

        try:
            file_op(file_path, dest_path)
            print(f"{'移动' if move_files_instead_of_copy else '复制'}: {filename} → {ext_folder}/")
        except Exception as e:
            print(f"处理失败: {filename} 错误: {e}")

    print("整理完成。")
    input("按任意键退出...")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        target_folder = sys.argv[1]
        if os.path.isdir(target_folder):
            classify_files(target_folder)
        else:
            print("错误：拖入的不是文件夹。")
            input("按任意键退出...")
    else:
        print("请将一个包含混合文件的文件夹拖拽到该脚本上。")
        input("按任意键退出...")
