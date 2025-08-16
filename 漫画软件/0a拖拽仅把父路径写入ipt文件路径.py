import os
import sys
import json

def update_itp_dirpath(file_path: str):
    file_path = os.path.abspath(file_path)
    parent_dir = os.path.dirname(file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"错误: 读取/解析失败 -> {file_path} ({e})")
        return

    if not isinstance(data, dict):
        print(f"错误: 非对象 JSON -> {file_path}")
        return

    data["dirPath"] = parent_dir  # 只修改路径，其他字段保持不变

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"已更新: {file_path}")
    except Exception as e:
        print(f"错误: 写入失败 -> {file_path} ({e})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: 将 .itp 文件拖拽到脚本上，或运行: python script.py file1.itp [file2.itp ...]")
        sys.exit(1)

    for p in sys.argv[1:]:
        if p.lower().endswith(".itp") and os.path.isfile(p):
            update_itp_dirpath(p)