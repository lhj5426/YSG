import os
import sys
import json
import copy

# ==============================================================================
# ======================== 配置区: 在这里设置你的区域合并规则 ========================
# ==============================================================================

# 1. 【首要】合并模式 (MERGE_MODE)
#    - 这个参数决定了脚本执行合并操作的顺序。
#
#    可选值 (请从下面选择一个填入):
#      "HORIZONTAL"               --> 【推荐】只进行横向合并 (合并水平相邻的框)。
#      "VERTICAL"                 --> 只进行纵向合并。
#      "HORIZONTAL_THEN_VERTICAL" --> 先横向合并，再对结果进行纵向合并。
#      "VERTICAL_THEN_HORIZONTAL" --> 先纵向合并，再对结果进行横向合并。
#      "NONE"                     --> 不执行任何合并操作。
MERGE_MODE = "HORIZONTAL"

# 2. 【最高优先级】从不参与合并的标签 (LABELS_TO_EXCLUDE_FROM_MERGE)
#    - 这是一个"黑名单"。所有标签名在此列表中的标注框将【完全不参与】任何合并操作。
LABELS_TO_EXCLUDE_FROM_MERGE = {"other"}

# 3. 【精细化合并控制】特定标签组合并规则 (SPECIFIC_MERGE_GROUPS)
#    - 这个功能让您可以精确控制哪些标签可以相互合并
#    - 如果启用此功能，只有在同一组内的标签才能相互合并
#    - 格式: 每个列表代表一个合并组，组内的标签可以相互合并
#    
#    启用方式: 设置 USE_SPECIFIC_MERGE_GROUPS = True
#    禁用方式: 设置 USE_SPECIFIC_MERGE_GROUPS = False (将使用通用的 REQUIRE_SAME_LABEL 规则)
USE_SPECIFIC_MERGE_GROUPS = True

SPECIFIC_MERGE_GROUPS = [
    # 第一组: balloon系列可以相互合并
    ["balloon", "balloon2"],
    
    # 第二组: qipao系列可以相互合并  
   # ["qipao", "qipao2"],
    
    # 第三组: changfangtiao系列可以相互合并
    #["changfangtiao", "changfangtiao2"],
    
    # 可以添加更多组...
    # ["fangkuai", "another_label"],  # 示例：如果需要fangkuai与其他标签合并
]

# 注意：
# - 不在任何组中的标签（如 fangkuai, kuangwai）将不会参与合并
# - 黑名单 (LABELS_TO_EXCLUDE_FROM_MERGE) 优先级最高，即使在合并组中也不会合并
# - 同组内的标签可以: balloon+balloon, balloon2+balloon2, balloon+balloon2 等任意组合

# 4. 是否要求标签相同才能合并？ (REQUIRE_SAME_LABEL)
#    - 这个规则【只在 USE_SPECIFIC_MERGE_GROUPS = False 时生效】
#    - 当启用精细化合并控制时，此设置会被忽略
#    - False: 【推荐】任何不在黑名单中的框，只要满足几何条件，都会被合并
REQUIRE_SAME_LABEL = False

# 5. 合并不同标签时的标签处理策略 (LABEL_MERGE_STRATEGY)
#    - 当两个不同标签的框被合并时，如何处理新框的标签
#    - "FIRST": 使用第一个框的标签
#    - "COMBINE": 组合两个标签，用 "+" 连接 (例如: "balloon+balloon2")
#    - "PREFER_NON_DEFAULT": 如果其中一个是默认标签(如"label")，则使用另一个；否则使用第一个
#    - "PREFER_SHORTER": 使用较短的标签名（如 "balloon" 优于 "balloon2"）
LABEL_MERGE_STRATEGY = "PREFER_SHORTER"

# 5. 纵向合并的几何参数 (VERTICAL_MERGE_PARAMS)
#    - 控制【纵向合并】的判断条件。
VERTICAL_MERGE_PARAMS = {
    # 最大垂直间隙 (像素)。两个框上下边缘的最大缝隙。
    "max_vertical_gap": 200,

    # 最小宽度重叠比例 (%)。两个框水平重叠部分占窄框宽度的最小百分比。
    "min_width_overlap_ratio": 30,
}

# 6. 横向合并的几何参数 (HORIZONTAL_MERGE_PARAMS)
#    - 控制【横向合并】的判断条件。
HORIZONTAL_MERGE_PARAMS = {
    # 最大水平间隙 (像素)。两个框左右边缘的最大缝隙。
    "max_horizontal_gap": 10, # 通常可以设置得比较大

    # 最小高度重叠比例 (%)。两个框垂直重叠部分占矮框高度的最小百分比。
    "min_height_overlap_ratio": 10,  # 降低到30%，更容易合并
}

# 7. 是否合并包含关系的矩形 (MERGE_CONTAINED_BOXES)
#    - True: 当一个矩形完全包含在另一个矩形内时，会被合并（保留外层矩形）
#    - False: 不处理包含关系的矩形
MERGE_CONTAINED_BOXES = True

# 8. 高级合并选项 (ADVANCED_MERGE_OPTIONS)
ADVANCED_MERGE_OPTIONS = {
    # 是否合并有任何重叠的矩形（不管重叠比例）
    "merge_any_overlap": True,
    
    # 是否允许负间隙（即重叠）在间隙计算中
    "allow_negative_gap": True,
    
    # 调试模式：显示详细的合并判断信息
    "debug_mode": False,
}
# --- 配置区结束 ---
# ==============================================================================


def get_bounding_box(shape):
    """
    辅助函数：从一个 shape 对象中提取其外接矩形的四个坐标。
    返回: 列表 [x_min, y_min, x_max, y_max]
    """
    points = shape['points']
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

def get_merge_group_for_label(label):
    """
    获取指定标签所属的合并组编号
    返回: 组编号 (从0开始)，如果不在任何组中则返回 -1
    """
    if not USE_SPECIFIC_MERGE_GROUPS:
        return -1
        
    for group_index, group in enumerate(SPECIFIC_MERGE_GROUPS):
        if label in group:
            return group_index
    return -1

def can_labels_merge(label1, label2):
    """
    判断两个标签是否可以合并
    """
    # 黑名单检查（最高优先级）
    if label1 in LABELS_TO_EXCLUDE_FROM_MERGE or label2 in LABELS_TO_EXCLUDE_FROM_MERGE:
        return False
    
    # 如果启用精细化合并控制
    if USE_SPECIFIC_MERGE_GROUPS:
        group1 = get_merge_group_for_label(label1)
        group2 = get_merge_group_for_label(label2)
        
        # 只有在同一组内的标签才能合并
        return group1 != -1 and group1 == group2
    
    # 否则使用通用规则
    if REQUIRE_SAME_LABEL:
        return label1 == label2
    else:
        return True  # 任何不在黑名单中的标签都可以合并

def merge_labels(label1, label2, strategy):
    """
    根据策略合并两个标签
    """
    if strategy == "FIRST":
        return label1
    elif strategy == "COMBINE":
        if label1 == label2:
            return label1
        return f"{label1}+{label2}"
    elif strategy == "PREFER_NON_DEFAULT":
        default_labels = {"label", ""}
        if label1 in default_labels and label2 not in default_labels:
            return label2
        elif label2 in default_labels and label1 not in default_labels:
            return label1
        else:
            return label1
    elif strategy == "PREFER_SHORTER":
        if label1 == label2:
            return label1
        elif len(label1) <= len(label2):
            return label1
        else:
            return label2
    else:
        return label1

def create_shape_from_box(box, shape1, shape2):
    """
    辅助函数：根据一个新的边界框坐标和两个参考的 shape 对象，创建一个新的 shape 对象。
    新的 shape 会继承第一个 shape 的属性，但标签会根据策略处理。
    """
    new_shape = copy.deepcopy(shape1)
    x_min, y_min, x_max, y_max = box
    new_shape['points'] = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
    
    # 处理标签合并
    label1 = shape1.get('label', '')
    label2 = shape2.get('label', '')
    new_shape['label'] = merge_labels(label1, label2, LABEL_MERGE_STRATEGY)
    
    return new_shape

def has_any_overlap(box1, box2):
    """
    检查两个矩形是否有任何重叠（包括边缘接触）
    """
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    # 检查是否在水平和垂直方向都有重叠或接触
    x_overlap = x1_max >= x2_min and x2_max >= x1_min
    y_overlap = y1_max >= y2_min and y2_max >= y1_min
    
    return x_overlap and y_overlap

def is_box_contained(box1, box2):
    """
    检查 box1 是否完全包含在 box2 内，或者 box2 是否完全包含在 box1 内
    返回: (is_contained, larger_box_index)
    - is_contained: 是否存在包含关系
    - larger_box_index: 0 表示 box1 更大，1 表示 box2 更大
    """
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    # 检查 box1 是否包含 box2
    if x1_min <= x2_min and y1_min <= y2_min and x1_max >= x2_max and y1_max >= y2_max:
        return True, 0  # box1 更大
    
    # 检查 box2 是否包含 box1
    if x2_min <= x1_min and y2_min <= y1_min and x2_max >= x1_max and y2_max >= y1_max:
        return True, 1  # box2 更大
    
    return False, -1

def can_merge_shapes(shape1, shape2, mode, params):
    """
    判断两个 shape 是否可以合并
    """
    label1 = shape1.get('label', '')
    label2 = shape2.get('label', '')
    
    # 使用新的标签合并检查函数
    if not can_labels_merge(label1, label2):
        if ADVANCED_MERGE_OPTIONS["debug_mode"]:
            if USE_SPECIFIC_MERGE_GROUPS:
                group1 = get_merge_group_for_label(label1)
                group2 = get_merge_group_for_label(label2)
                print(f"    调试: 跳过合并 - 标签不在同一合并组: '{label1}'(组{group1}) 和 '{label2}'(组{group2})")
            else:
                print(f"    调试: 跳过合并 - 标签规则不允许: '{label1}' 和 '{label2}'")
        return False
    
    box1, box2 = get_bounding_box(shape1), get_bounding_box(shape2)
    
    if ADVANCED_MERGE_OPTIONS["debug_mode"]:
        print(f"    调试: 检查合并 {label1} {box1} 和 {label2} {box2}")
    
    # 首先检查包含关系
    if MERGE_CONTAINED_BOXES:
        is_contained, _ = is_box_contained(box1, box2)
        if is_contained:
            if ADVANCED_MERGE_OPTIONS["debug_mode"]:
                print(f"    调试: 可以合并 - 包含关系")
            return True
    
    # 检查是否有任何重叠（如果启用此选项）
    if ADVANCED_MERGE_OPTIONS["merge_any_overlap"]:
        if has_any_overlap(box1, box2):
            if ADVANCED_MERGE_OPTIONS["debug_mode"]:
                print(f"    调试: 可以合并 - 有重叠")
            return True
    
    # 然后检查相邻/重叠关系
    if mode == "VERTICAL":
        # 检查水平重叠
        overlap_x = max(0, min(box1[2], box2[2]) - max(box1[0], box2[0]))
        min_width = min(box1[2] - box1[0], box2[2] - box2[0])
        if min_width <= 0:
            return False
        
        overlap_ratio_w = (overlap_x / min_width) * 100
        
        # 检查垂直间隙
        vertical_gap = max(box1[1], box2[1]) - min(box1[3], box2[3])
        
        can_merge = (overlap_ratio_w >= params["min_width_overlap_ratio"] and 
                    (0 <= vertical_gap <= params["max_vertical_gap"] or 
                     (ADVANCED_MERGE_OPTIONS["allow_negative_gap"] and vertical_gap <= params["max_vertical_gap"])))
        
        if ADVANCED_MERGE_OPTIONS["debug_mode"]:
            print(f"    调试: 纵向合并检查 - 重叠比例: {overlap_ratio_w:.1f}% (需要>={params['min_width_overlap_ratio']}%), 垂直间隙: {vertical_gap} (需要<={params['max_vertical_gap']}), 结果: {can_merge}")
        
        return can_merge
    
    else: # HORIZONTAL
        # 检查垂直重叠
        overlap_y = max(0, min(box1[3], box2[3]) - max(box1[1], box2[1]))
        min_height = min(box1[3] - box1[1], box2[3] - box2[1])
        if min_height <= 0:
            return False
        
        overlap_ratio_h = (overlap_y / min_height) * 100
        
        # 检查水平间隙
        horizontal_gap = max(box1[0], box2[0]) - min(box1[2], box2[2])
        
        can_merge = (overlap_ratio_h >= params["min_height_overlap_ratio"] and 
                    (0 <= horizontal_gap <= params["max_horizontal_gap"] or 
                     (ADVANCED_MERGE_OPTIONS["allow_negative_gap"] and horizontal_gap <= params["max_horizontal_gap"])))
        
        if ADVANCED_MERGE_OPTIONS["debug_mode"]:
            print(f"    调试: 横向合并检查 - 重叠比例: {overlap_ratio_h:.1f}% (需要>={params['min_height_overlap_ratio']}%), 水平间隙: {horizontal_gap} (需要<={params['max_horizontal_gap']}), 结果: {can_merge}")
        
        return can_merge

def perform_merge(shapes, mode):
    """
    核心合并函数：对输入的 shapes 列表执行单次合并（纵向或横向）。
    它会持续循环，直到找不到任何可以合并的框为止，确保所有可能的合并都已完成。
    """
    params = VERTICAL_MERGE_PARAMS if mode == "VERTICAL" else HORIZONTAL_MERGE_PARAMS
    
    merge_count = 0
    while True:
        merged_in_pass = False
        i = 0
        while i < len(shapes):
            j = i + 1
            while j < len(shapes):
                shape1, shape2 = shapes[i], shapes[j]
                
                if can_merge_shapes(shape1, shape2, mode, params):
                    # 检查是否是包含关系
                    box1, box2 = get_bounding_box(shape1), get_bounding_box(shape2)
                    is_contained, larger_index = is_box_contained(box1, box2)
                    
                    if is_contained and MERGE_CONTAINED_BOXES:
                        # 包含关系：保留更大的框，使用包含框的标签策略
                        if larger_index == 0:
                            # box1 包含 box2，保留 box1 的坐标但处理标签
                            new_shape = create_shape_from_box(box1, shape1, shape2)
                            merge_type = "包含合并"
                        else:
                            # box2 包含 box1，保留 box2 的坐标但处理标签
                            new_shape = create_shape_from_box(box2, shape1, shape2)
                            merge_type = "包含合并"
                    else:
                        # 相邻/重叠关系：创建包围两个框的最大矩形
                        merged_box = [min(box1[0], box2[0]), min(box1[1], box2[1]), 
                                    max(box1[2], box2[2]), max(box1[3], box2[3])]
                        new_shape = create_shape_from_box(merged_box, shape1, shape2)
                        merge_type = f"{mode}合并"
                    
                    # 移除原来的两个 shape，插入新的合并后的 shape
                    shapes.pop(j)
                    shapes.pop(i)
                    shapes.insert(i, new_shape)
                    
                    merged_in_pass = True
                    merge_count += 1
                    
                    # 输出合并信息（可选，用于调试）
                    if not can_labels_merge(shape1.get('label'), shape2.get('label')) or shape1.get('label') != shape2.get('label'):
                        print(f"    {merge_type}: '{shape1.get('label')}' + '{shape2.get('label')}' -> '{new_shape.get('label')}'")
                    elif is_contained:
                        print(f"    包含关系合并: '{shape1.get('label')}' -> '{new_shape.get('label')}'")
                    
                    break
                else:
                    j += 1
            
            if merged_in_pass:
                break
            else:
                i += 1
        
        if not merged_in_pass:
            break
    
    if merge_count > 0:
        print(f"    {mode} 合并: 执行了 {merge_count} 次合并操作")
            
    return shapes

def process_file(file_path):
    """处理单个JSON文件的完整流程"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f: 
            data = json.load(f)
    except Exception as e:
        print(f"  - 错误: 读取文件 '{os.path.basename(file_path)}' 时失败: {e}")
        return False
    
    if 'shapes' not in data or not data['shapes']: 
        print(f"  - 跳过: {os.path.basename(file_path)} (无标注框)")
        return False
    
    initial_shapes = copy.deepcopy(data['shapes'])
    initial_count = len(data['shapes'])
    
    if MERGE_MODE == "NONE": 
        print(f"  - 跳过: {os.path.basename(file_path)} (合并模式为NONE)")
        return False
    
    print(f"  - 处理: {os.path.basename(file_path)} (初始框数: {initial_count})")
    
    final_shapes = []
    if MERGE_MODE == "VERTICAL": 
        final_shapes = perform_merge(initial_shapes, "VERTICAL")
    elif MERGE_MODE == "HORIZONTAL": 
        final_shapes = perform_merge(initial_shapes, "HORIZONTAL")
    elif MERGE_MODE == "VERTICAL_THEN_HORIZONTAL":
        temp_shapes = perform_merge(initial_shapes, "VERTICAL")
        final_shapes = perform_merge(temp_shapes, "HORIZONTAL")
    elif MERGE_MODE == "HORIZONTAL_THEN_VERTICAL":
        temp_shapes = perform_merge(initial_shapes, "HORIZONTAL")
        final_shapes = perform_merge(temp_shapes, "VERTICAL")
        
    data['shapes'] = final_shapes
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"    完成: 框数 {initial_count} -> {len(final_shapes)} (减少了 {initial_count - len(final_shapes)} 个框)")
        return True
    except Exception as e:
        print(f"  - 错误: 写入文件 '{os.path.basename(file_path)}' 时失败: {e}")
        return False

def main():
    """脚本主入口函数"""
    print("="*60)
    print("区域合并脚本 (精细化标签控制版)")
    print(f"合并模式: {MERGE_MODE}")
    print(f"精细化合并控制: {'启用' if USE_SPECIFIC_MERGE_GROUPS else '禁用'}")
    
    if USE_SPECIFIC_MERGE_GROUPS:
        print("合并组设置:")
        for i, group in enumerate(SPECIFIC_MERGE_GROUPS):
            print(f"  组{i}: {group}")
        print(f"不在任何组中的标签将不会合并")
    else:
        print(f"要求相同标签: {'是' if REQUIRE_SAME_LABEL else '否'}")
    
    print(f"合并包含关系矩形: {'是' if MERGE_CONTAINED_BOXES else '否'}")
    print(f"标签合并策略: {LABEL_MERGE_STRATEGY}")
    print(f"排除合并的标签: {list(LABELS_TO_EXCLUDE_FROM_MERGE) if LABELS_TO_EXCLUDE_FROM_MERGE else '无'}")
    print(f"调试模式: {'开启' if ADVANCED_MERGE_OPTIONS['debug_mode'] else '关闭'}")
    print("="*60 + "\n")

    files_to_process = []
    if len(sys.argv) > 1:
        print("进入 [拖拽模式]...")
        unique_json_paths = set()
        for path in sys.argv[1:]:
            if os.path.isfile(path) and path.lower().endswith('.json'):
                unique_json_paths.add(os.path.abspath(path))
            elif os.path.isdir(path):
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        if filename.lower().endswith('.json'):
                            unique_json_paths.add(os.path.join(root, filename))
        files_to_process = sorted(list(unique_json_paths))
    else:
        print("进入 [双击模式]...")
        try:
            work_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            work_dir = os.getcwd()
        print(f"扫描目录: {work_dir}")
        files_to_process = [os.path.join(work_dir, f) for f in os.listdir(work_dir) if f.lower().endswith('.json')]
    
    if not files_to_process:
        print("\n未找到任何 .json 文件进行处理。")
        input("按 Enter 键退出...")
        return
        
    print(f"\n找到 {len(files_to_process)} 个目标JSON文件，开始处理...\n")
    processed_count = 0
    for file_path in files_to_process:
        if file_path == os.path.abspath(__file__): 
            continue
        if process_file(file_path):
            processed_count += 1
            
    print(f"\n处理完成！总共修改了 {processed_count} 个 JSON 文件。")
    input("按 Enter 键退出...")

if __name__ == "__main__":
    main()