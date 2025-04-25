import os
import sys
import re

def count_images_in_benpian(folder_path):
    """
    查找传入文件夹下的 "本篇" 子文件夹，递归统计其中的图片数量。
    支持的图片格式：.jpg, .jpeg, .png, .gif, .bmp, .webp
    """
    benpian_path = os.path.join(folder_path, "本篇")
    if not os.path.isdir(benpian_path):
        print(f"警告：在 {folder_path} 中未找到 '本篇' 文件夹，跳过统计！")
        return 0

    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    image_count = 0
    for root, dirs, files in os.walk(benpian_path):
        for f in files:
            if f.lower().endswith(valid_extensions):
                image_count += 1
    return image_count

def remove_existing_prefix(folder_name):
    """
    如果文件夹名称以形如 "[数字]" 的格式开头，则删除该前缀。
    """
    new_name = re.sub(r'^\[\d+\]', '', folder_name).strip()
    return new_name

def rename_folder(folder_path, count):
    """
    根据统计出的图片数量，在原文件夹名称开头添加前缀 "[数量]"。
    如果原名称已存在形如 "[数字]" 的前缀，则先删除后添加新的。
    """
    parent_dir = os.path.dirname(folder_path)
    folder_name = os.path.basename(folder_path)
    new_folder_base = remove_existing_prefix(folder_name)
    new_folder_name = f"[{count}]{new_folder_base}"
    new_folder_path = os.path.join(parent_dir, new_folder_name)
    
    if new_folder_path != folder_path:
        try:
            os.rename(folder_path, new_folder_path)
            print(f"文件夹重命名成功：\n  原路径：{folder_path}\n  新路径：{new_folder_path}")
            return new_folder_path
        except Exception as e:
            print(f"文件夹重命名失败：{folder_path} -> {new_folder_path}\n错误：{e}")
            return folder_path
    else:
        print(f"文件夹名称未发生变化：{folder_path}")
        return folder_path

def process_folder(folder_path):
    """
    对单个文件夹进行处理：
      1. 在其 "本篇" 子文件夹中统计图片数量；
      2. 根据统计结果修改文件夹名称。
    """
    if not os.path.isdir(folder_path):
        print(f"错误：{folder_path} 不是有效的文件夹")
        return

    count = count_images_in_benpian(folder_path)
    print(f"文件夹 {folder_path} 中 '本篇' 下图片数量：{count}")
    new_folder_path = rename_folder(folder_path, count)
    return new_folder_path

def main():
    folder_paths = sys.argv[1:]
    if not folder_paths:
        print("请将文件夹拖拽到本脚本上运行！")
        input("按任意键退出...")
        return

    for folder in folder_paths:
        process_folder(folder)
    
    input("\n处理完成！按任意键退出...")

if __name__ == "__main__":
    main()
