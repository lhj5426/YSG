import os
import sys
import shutil

def merge_yolo_subfolders(yolo_root):
    print(f"开始处理目录: {yolo_root}")

    img_exts = ('.png', '.jpg', '.jpeg')
    images_dir = os.path.join(yolo_root, '图片')
    labels_dir = os.path.join(yolo_root, '标签')

    # 创建目标文件夹
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)

    moved_images = 0
    moved_labels = 0

    # 遍历 YOLO 根目录下的子文件夹
    for root, dirs, files in os.walk(yolo_root):
        if root in [images_dir, labels_dir]:
            continue
        if root == yolo_root:
            continue

        for f in files:
            src_path = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()

            if ext in img_exts:
                dst_path = os.path.join(images_dir, f)
                file_type = "图片"
            elif ext == '.txt':
                dst_path = os.path.join(labels_dir, f)
                file_type = "标签"
            else:
                continue

            # 如果目标文件存在，重命名避免覆盖
            if os.path.exists(dst_path):
                base, ext_ = os.path.splitext(f)
                count = 1
                while True:
                    new_name = f"{base}_{count}{ext_}"
                    new_dst = os.path.join(images_dir if ext in img_exts else labels_dir, new_name)
                    if not os.path.exists(new_dst):
                        dst_path = new_dst
                        break
                    count += 1

            try:
                shutil.move(src_path, dst_path)
                print(f"移动{file_type}: {src_path} -> {dst_path}")
                if file_type == "图片":
                    moved_images += 1
                else:
                    moved_labels += 1
            except Exception as e:
                print(f"移动失败: {src_path} 错误: {e}")

    # 删除空目录
    for root, dirs, files in os.walk(yolo_root, topdown=False):
        if root in [images_dir, labels_dir, yolo_root]:
            continue
        if not os.listdir(root):
            try:
                os.rmdir(root)
                print(f"删除空文件夹: {root}")
            except Exception as e:
                print(f"删除空文件夹失败: {root} 错误: {e}")

    print("\n合并完成！")
    print(f"图片文件夹: {images_dir}，共移动 {moved_images} 个文件")
    print(f"标签文件夹: {labels_dir}，共移动 {moved_labels} 个文件")

    # ========== 移动到上一层 ==========
    parent_dir = os.path.dirname(yolo_root)
    final_images_path = os.path.join(parent_dir, '图片')
    final_labels_path = os.path.join(parent_dir, '标签')

    # 如果存在就删除
    if os.path.exists(final_images_path):
        shutil.rmtree(final_images_path)
        print(f"已删除原有图片目录: {final_images_path}")
    if os.path.exists(final_labels_path):
        shutil.rmtree(final_labels_path)
        print(f"已删除原有标签目录: {final_labels_path}")

    # 移动目录
    shutil.move(images_dir, final_images_path)
    shutil.move(labels_dir, final_labels_path)

    print("\n已将 '图片' 和 '标签' 移动至上级目录：")
    print(f"图片目录: {final_images_path}")
    print(f"标签目录: {final_labels_path}")

    # ========== 删除 YOLO 空文件夹 ==========
    if not os.listdir(yolo_root):
        try:
            os.rmdir(yolo_root)
            print(f"\n已删除空的 YOLO 文件夹: {yolo_root}")
        except Exception as e:
            print(f"\n删除 YOLO 文件夹失败: {yolo_root} 错误: {e}")
    else:
        print(f"\n保留 YOLO 文件夹（非空）: {yolo_root}")

    input("\n操作完成，按任意键关闭窗口...")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        yolo_folder = sys.argv[1]
        if not os.path.isdir(yolo_folder):
            print(f"错误：路径不是文件夹: {yolo_folder}")
            input("按任意键退出...")
        else:
            merge_yolo_subfolders(yolo_folder)
    else:
        print("请拖拽 YOLO 根目录到脚本上运行。")
        input("按任意键退出...")
