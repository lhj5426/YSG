import os
import json
from typing import Dict, List

# ====================== 可配置区域（直接在这里改） ======================
# 映射关系：把键替换为值。按需增删即可。
LABEL_MAP: Dict[str, str] = {
    "balloon": "shuqing",
    # "balloon2": "balloon",
    # "changfangtiao2": "changfangtiao",
    # 例子：把 A 改成 B
    # "A": "B",
}

# 目标目录：
# - None 表示使用脚本所在目录
# - 或填写绝对/相对路径，例如 r"D:\dataset\ann"
TARGET_DIR: str | None = None

# 需要识别为“图片文件”的扩展名（用于匹配同名 JSON）
IMAGE_EXTS: List[str] = [".jpg", ".jpeg", ".png", ".bmp", ".gif"]

# 处理结束后是否等待按键（便于双击运行）
PAUSE_ON_EXIT: bool = True
# =======================================================================


def revert_json_file(json_path: str, labels_to_revert: Dict[str, str]):
    """
    处理单个 JSON 文件，根据 labels_to_revert 将标签替换。
    """
    print(f"--- 正在处理文件: {os.path.basename(json_path)} ---")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"错误：无法读取或解析 JSON 文件 {json_path}。原因: {e}")
        return

    if 'shapes' not in data or not isinstance(data['shapes'], list):
        print(f"警告：在 {json_path} 中未找到 'shapes' 列表，已跳过。")
        return

    changes = 0
    for shape in data['shapes']:
        label = shape.get('label')
        if isinstance(label, str) and label in labels_to_revert:
            new_label = labels_to_revert[label]
            shape['label'] = new_label
            changes += 1
            print(f"  替换: '{label}' -> '{new_label}'")

    try:
        if changes > 0:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"--- 完成：{os.path.basename(json_path)}（{changes} 处替换）---\n")
        else:
            print(f"--- 未发现可替换标签：{os.path.basename(json_path)} ---\n")
    except Exception as e:
        print(f"错误：无法写入文件 {json_path}。原因: {e}")


def main():
    # 计算工作目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    work_dir = TARGET_DIR if TARGET_DIR else script_dir
    print(f"工作目录: {work_dir}\n")

    # 规范化扩展名
    image_exts = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in IMAGE_EXTS}

    # 校验映射
    mapping: Dict[str, str] = {}
    for k, v in LABEL_MAP.items():
        k2 = str(k).strip()
        v2 = str(v).strip()
        if not k2 or not v2:
            print(f"警告：忽略无效映射项（键或值为空）：{k} -> {v}")
            continue
        mapping[k2] = v2

    if not mapping:
        print("未设置任何映射。请在脚本顶部的 LABEL_MAP 中添加，例如：'A': 'B'")
        if PAUSE_ON_EXIT:
            input("\n按 Enter 退出...")
        return

    # 列出目录并处理
    try:
        filenames = os.listdir(work_dir)
    except Exception as e:
        print(f"错误：无法列出目录 {work_dir}。原因：{e}")
        if PAUSE_ON_EXIT:
            input("\n按 Enter 退出...")
        return

    found_files = False
    for filename in filenames:
        base_name, extension = os.path.splitext(filename)
        if extension.lower() in image_exts:
            json_filename = base_name + '.json'
            json_path = os.path.join(work_dir, json_filename)

            if os.path.exists(json_path):
                found_files = True
                revert_json_file(json_path, mapping)
            else:
                print(f"未找到与图片 '{filename}' 对应的 JSON：'{json_filename}'，已跳过。\n")

    if not found_files:
        print("未在目标目录中找到任何匹配的图片和 JSON 文件对。")

    if PAUSE_ON_EXIT:
        input("\n处理完成。按 Enter 退出...")


if __name__ == "__main__":
    main()