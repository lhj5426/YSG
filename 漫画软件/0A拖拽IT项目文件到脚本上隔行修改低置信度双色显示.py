import sys
import os
import json

def process_json(obj, fontstyle_counter):
    """
    递归处理 JSON 对象：
    每当遇到 "fontstyle"，按次数计数，每隔一个进行处理。
    这个函数本身不关心“页”，只关心它被调用的对象范围。
    """
    if isinstance(obj, dict):
        # 如果当前对象包含 "fontstyle"，计数器 +1
        if "fontstyle" in obj:
            fontstyle_counter[0] += 1
            if fontstyle_counter[0] % 2 == 0:  # 每隔一个（即第2、4、6...个）
                # 如果有 "probability" 键且其值为 1，则修改为 0
                if "probability" in obj and obj["probability"] == 1:
                    obj["probability"] = 0
                # 如果没有 "probability" 键，则添加它并设置值为 0
                elif "probability" not in obj:
                    obj["probability"] = 0

        # 对当前对象的所有子项进行递归处理
        for key in obj:
            process_json(obj[key], fontstyle_counter)

    elif isinstance(obj, list):
        # 如果是列表，则遍历列表中的每一项进行递归处理
        for item in obj:
            process_json(item, fontstyle_counter)

def main():
    if len(sys.argv) < 2:
        print("用法: 请将 JSON 格式的 IPA 项目文件拖拽到此脚本上执行。")
        # 添加 input() 使得窗口在双击执行时不会立即关闭
        input("按 Enter 键退出...")
        return

    file_path = sys.argv[1]
    if not os.path.isfile(file_path):
        print(f"错误: 文件不存在 -> {file_path}")
        input("按 Enter 键退出...")
        return

    try:
        # 读取整个 JSON 文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # --- 核心修改部分 ---
        # 遍历 JSON 数据中的每一个顶级键值对（我们假设每个键代表一页）
        for page_name, page_data in data.items():
            print(f"正在处理页面: {page_name}...")
            # 为每一页创建一个新的、从0开始的计数器
            fontstyle_counter = [0]
            # 对当前页面的数据进行处理
            process_json(page_data, fontstyle_counter)
            print(f"页面 {page_name} 处理完成。")

        # 处理完成后，将修改后的 `data` 对象覆盖写回原文件
        with open(file_path, 'w', encoding='utf-8') as f:
            # 使用 indent=4 格式化输出，ensure_ascii=False 保证中文正常显示
            json.dump(data, f, ensure_ascii=False, indent=4)

        print("\n所有页面处理完成，已直接覆盖源文件。")

    except json.JSONDecodeError as e:
        print(f"错误: 文件不是有效的 JSON 格式。 -> {file_path}")
        print(f"详细信息: {e}")
    except Exception as e:
        print(f"处理过程中发生未知错误: {e}")
    
    input("按 Enter 键退出...")

if __name__ == '__main__':
    main()