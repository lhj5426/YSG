import os
import json

# ==============================================================================
# --- 配置区: 工作流排序规则 ---
#
# 1. 特殊置顶标签 (EXCEPTION_LABEL)
#    - 设置一个特殊的标签。所有带有此标签的标注将被无条件地移动到列表最顶端。
#    - 这些标注将不会参与下面的空间排序。
#
EXCEPTION_LABEL = "other"
#
# 2. 空间排序模式 (SPATIAL_SORT_MODE)
#    - 这个模式将应用于 **除了特殊置顶标签之外的所有其他标签**。
#    - 所有其他标签会被看作一个整体，然后根据这个模式进行空间排序。
#    - 可用选项:
#      --- 从右到左 (适用于漫画) ---
#      "REV_X_THEN_Y"  --> **【强烈推荐】** 先从右到左分栏, 再从上到下排序
#      "Y_THEN_REV_X"  --> 先从上到下分行, 再从右到左排序
#      "REV_X"         --> 仅横坐标 (严格从右到左)
#      --- 从左到右 ---
#      "X_THEN_Y"      --> 先从左到右, 再从上到下
#      "Y_THEN_X"      --> 先从上到下, 再从左到右
#      --- 其他 ---
#      "NONE"          --> 不进行空间排序 (仅将特殊标签置顶)
#
SPATIAL_SORT_MODE = "REV_X"
#
# --- 配置区结束 ---
# ==============================================================================

def get_bounding_box_top_left(points):
    """从点列表中计算出边界框的左上角坐标 (x_min, y_min)"""
    if not points: return (0, 0)
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    return (min(x_coords), min(y_coords))

def sort_shapes_in_file(file_path):
    """
    读取JSON文件，根据新的工作流规则进行排序，然后写回文件。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"  - 错误: 读取或解析文件 '{os.path.basename(file_path)}' 时失败: {e}")
        return False

    if not isinstance(data, dict) or 'shapes' not in data or not isinstance(data['shapes'], list):
        print(f"  - 警告: 文件 '{os.path.basename(file_path)}' 结构不符，已跳过。")
        return False

    # --- 全新的核心排序逻辑 ---
    def create_workflow_sort_key(shape):
        label = shape.get('label')
        points = shape.get('points', [])
        x_min, y_min = get_bounding_box_top_left(points)

        # 第一级排序: 判断是否为特殊置顶标签
        # 如果是，它属于第 0 组；否则属于第 1 组。
        primary_group = 0 if label == EXCEPTION_LABEL else 1

        # 第二级和第三级排序: 应用空间规则
        # 只有第 1 组（非特殊标签）才需要关心空间位置
        if primary_group == 0:
            # 对于特殊标签，空间位置不重要，给一个固定值即可
            return (primary_group, 0, 0)
        else:
            # 对于其他所有标签，应用配置好的空间排序模式
            if SPATIAL_SORT_MODE == "REV_X_THEN_Y":
                return (primary_group, -x_min, y_min)
            elif SPATIAL_SORT_MODE == "Y_THEN_REV_X":
                return (primary_group, y_min, -x_min)
            elif SPATIAL_SORT_MODE == "REV_X":
                return (primary_group, -x_min, 0)
            elif SPATIAL_SORT_MODE == "X_THEN_Y":
                return (primary_group, x_min, y_min)
            elif SPATIAL_SORT_MODE == "Y_THEN_X":
                return (primary_group, y_min, x_min)
            elif SPATIAL_SORT_MODE == "X":
                return (primary_group, x_min, 0)
            elif SPATIAL_SORT_MODE == "Y":
                return (primary_group, y_min, 0)
            else: # "NONE"
                return (primary_group, 0, 0)

    data['shapes'].sort(key=create_workflow_sort_key)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"  - 错误: 写入文件 '{os.path.basename(file_path)}' 时失败: {e}")
        return False

def main():
    try:
        work_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        work_dir = os.getcwd()

    print(f"正在扫描并处理目录: {work_dir}")
    print(f"特殊置顶标签: '{EXCEPTION_LABEL}'")
    print(f"其余标签空间排序模式: {SPATIAL_SORT_MODE}\n")

    json_files = [f for f in os.listdir(work_dir) if f.lower().endswith('.json')]
    
    if not json_files:
        print("错误：在当前目录下未找到任何 .json 文件。")
        input("\n按 Enter 键退出...")
        return
        
    processed_count = 0
    for filename in json_files:
        if filename == os.path.basename(__file__): continue
        file_path = os.path.join(work_dir, filename)
        if sort_shapes_in_file(file_path):
            print(f"  - 已排序: {filename}")
            processed_count += 1
            
    print(f"\n处理完成！总共修改了 {processed_count} 个 JSON 文件。")
    input("按 Enter 键退出...")

if __name__ == "__main__":
    main()