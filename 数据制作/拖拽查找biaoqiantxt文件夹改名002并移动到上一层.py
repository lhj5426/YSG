import sys
import os
import shutil

def print_step(message):
    print(message)
    print()

def find_and_move(folder_path):
    for root, dirs, files in os.walk(folder_path):
        if "biaoqianTXT" in dirs:
            old_path = os.path.join(root, "biaoqianTXT")
            new_path = os.path.join(root, "002")
            
            print_step(f"找到目标文件夹：\n{old_path}")

            if os.path.exists(new_path):
                print_step(f"原路径下已有 '002' 文件夹，准备删除：\n{new_path}")
                shutil.rmtree(new_path)
                print("→ 已删除原有 002 文件夹\n")

            os.rename(old_path, new_path)
            print_step(f"已重命名为：\n{new_path}")

            parent_dir = os.path.dirname(root)
            target_path = os.path.join(parent_dir, "002")

            if os.path.exists(target_path):
                print_step(f"目标路径已有 '002' 文件夹，准备删除：\n{target_path}")
                shutil.rmtree(target_path)
                print("→ 已删除目标目录中的 002 文件夹\n")

            shutil.move(new_path, target_path)
            print_step(f"已移动到：\n{target_path}")
            return

    print_step("未找到名为 'biaoqianTXT' 的文件夹")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请将文件夹拖拽到脚本上运行")
        os.system("pause")
        sys.exit(1)
    
    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print(f"路径无效：{folder}")
        os.system("pause")
        sys.exit(1)
    
    print_step(f"开始处理拖拽的文件夹：\n{folder}")
    find_and_move(folder)

    print("操作完成，按任意键关闭窗口")
    os.system("pause")
