import os
import sys

def unify_yolo_txt_format(txt_folder):
    for filename in os.listdir(txt_folder):
        if not filename.lower().endswith('.txt'):
            continue
        path = os.path.join(txt_folder, filename)
        lines_new = []
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue  # 格式错误，跳过
            class_id = parts[0]
            try:
                cx = float(parts[1])
                cy = float(parts[2])
                w = float(parts[3])
                h = float(parts[4])
            except:
                continue  # 转换失败跳过
            # 统一格式，保留6位小数，不带置信度
            line_new = f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
            lines_new.append(line_new)
        # 覆盖写回文件
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines_new) + '\n')
        print(f"已统一格式：{filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请将包含YOLO TXT文件的文件夹拖拽到此脚本上执行！")
        input("按任意键退出...")
        sys.exit(1)

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print("无效的文件夹路径！")
        input("按任意键退出...")
        sys.exit(1)

    unify_yolo_txt_format(folder)
    print("所有文件格式已统一为5列格式。")
    input("按任意键退出...")
