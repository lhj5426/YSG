import os
import sys
import json
import copy

# ==============================================================================
# ======================== 配置区: 在这里设置你的区域合并规则 ========================
# ==============================================================================

# 合并模式：
# - "VERTICAL" 仅按垂直方向规则合并（推荐你当前的需求）
# - "HORIZONTAL" 仅按水平方向规则合并
# - "VERTICAL_THEN_HORIZONTAL" 先垂直合并一轮，再水平合并一轮
# - "HORIZONTAL_THEN_VERTICAL" 先水平合并一轮，再垂直合并一轮
# - "NONE" 不进行任何合并
# 注意：对于横排文本（一行一行往下），依然使用 "VERTICAL" 模式，因为你是要合并垂直方向上相邻的框。
MERGE_MODE = "HORIZONTAL"

# ======================== 核心新增配置: 选择文本阅读方向 ========================
# <--- 在这里选择你要处理的文本类型
# - "VERTICAL_RTL": 用于竖排文字（从右到左阅读）。
#                   - 文本合并顺序: 右边的框 + 左边的框
#                   - 例子: 第一个气泡对话框的例子
# - "HORIZONTAL_TTB": 用于横排文字（从上到下阅读）。
#                   - 文本合并顺序: 上边的框 + "\n" + 下边的框
#                   - 例子: 第二个对话框的例子
TEXT_READING_DIRECTION = "VERTICAL_RTL"  # <-- 对于新图片，请使用这个设置

# 是否合并 "description" 字段中的文本内容
MERGE_DESCRIPTIONS = True

# 不同阅读方向下，文本合并时使用的分隔符
DESCRIPTION_SEPARATOR = {
    "VERTICAL_RTL": "",       # 竖排从右到左拼接，通常不需要分隔符
    "HORIZONTAL_TTB": "\n"    # 横排从上到下拼接，用换行符分隔每一行
}
# =========================================================================

# 从不参与合并的标签（黑名单）：一旦任一框的标签命中此集合，直接不允许与其它框合并
LABELS_TO_EXCLUDE_FROM_MERGE = {"other"}

# 是否启用“特定标签组”合并机制
USE_SPECIFIC_MERGE_GROUPS = False

# 指定可互相合并的标签组
SPECIFIC_MERGE_GROUPS = [
    ["balloon", "balloon2"],
    ["changfangtiao", "changfangtiao2"],
]

# 当未启用 SPECIFIC_MERGE_GROUPS 时，是否要求两个 shape 标签完全一致才允许合并
REQUIRE_SAME_LABEL = True

# 合并后如何确定新 shape 的标签
LABEL_MERGE_STRATEGY = "FIRST"

# 垂直合并参数
VERTICAL_MERGE_PARAMS = {
    # 最大垂直间隙（像素）。对于横排文字，这个值可以稍微大一点。
    "max_vertical_gap": 15,
    # 最小水平重叠比例（百分比）。对于横排文字，这个值可以设低一些，只要有部分对齐即可。
    "min_width_overlap_ratio": 50,
    "overlap_epsilon": 1e-6,
}

# 水平合并参数
HORIZONTAL_MERGE_PARAMS = {
    "max_horizontal_gap": 10,
    "min_height_overlap_ratio": 10,
    "overlap_epsilon": 1e-6,
}

MERGE_CONTAINED_BOXES = True

ADVANCED_MERGE_OPTIONS = {
    "merge_any_overlap": True,
    "allow_negative_gap": True,
    "debug_mode": False,
}
# --- 配置区结束 ---
# ==============================================================================


def get_bounding_box(shape):
    points = shape['points']
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

def get_merge_group_for_label(label):
    if not USE_SPECIFIC_MERGE_GROUPS:
        return -1
    for idx, group in enumerate(SPECIFIC_MERGE_GROUPS):
        if label in group:
            return idx
    return -1

def can_labels_merge(label1, label2):
    if label1 in LABELS_TO_EXCLUDE_FROM_MERGE or label2 in LABELS_TO_EXCLUDE_FROM_MERGE:
        return False
    if USE_SPECIFIC_MERGE_GROUPS:
        g1 = get_merge_group_for_label(label1)
        g2 = get_merge_group_for_label(label2)
        return g1 != -1 and g1 == g2
    if REQUIRE_SAME_LABEL:
        return label1 == label2
    return True

def merge_labels(label1, label2, strategy):
    if strategy == "FIRST":
        return label1
    elif strategy == "COMBINE":
        return label1 if label1 == label2 else f"{label1}+{label2}"
    elif strategy == "PREFER_NON_DEFAULT":
        default_labels = {"label", ""}
        if label1 in default_labels and label2 not in default_labels: return label2
        if label2 in default_labels and label1 not in default_labels: return label1
        return label1
    elif strategy == "PREFER_SHORTER":
        return label1 if len(label1) <= len(label2) else label2
    return label1

def create_shape_from_box(box, shape1, shape2):
    """
    根据合并后的外接矩形 box 与两个参考 shape 生成一个新的 shape。
    - description 的合并逻辑现在由全局配置 TEXT_READING_DIRECTION 控制。
    """
    new_shape = copy.deepcopy(shape1)
    x_min, y_min, x_max, y_max = box
    new_shape['points'] = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
    new_shape['label'] = merge_labels(shape1.get('label', ''), shape2.get('label', ''), LABEL_MERGE_STRATEGY)

    # ======================== 重构: 根据阅读方向合并 description 文本 ========================
    if MERGE_DESCRIPTIONS:
        desc1 = shape1.get('description', '')
        desc2 = shape2.get('description', '')

        if desc1 and desc2:
            merged_description = ""
            separator = DESCRIPTION_SEPARATOR.get(TEXT_READING_DIRECTION, "")
            b1 = get_bounding_box(shape1)
            b2 = get_bounding_box(shape2)

            if TEXT_READING_DIRECTION == "VERTICAL_RTL":
                # 竖排模式：按从右到左的顺序拼接文本
                # b[0] 是 x_min，值越大表示框越靠右
                if b1[0] > b2[0]: # shape1 在右边, shape2 在左边
                    merged_description = desc1 + separator + desc2
                else: # shape2 在右边, shape1 在左边
                    merged_description = desc2 + separator + desc1
            
            elif TEXT_READING_DIRECTION == "HORIZONTAL_TTB":
                # 横排模式：按从上到下的顺序拼接文本
                # b[1] 是 y_min, 值越小表示框越靠上
                if b1[1] < b2[1]: # shape1 在上面, shape2 在下面
                    merged_description = desc1 + separator + desc2
                else: # shape2 在上面, shape1 在下面
                    merged_description = desc2 + separator + desc1
            
            else:
                # 未知模式，默认拼接并给出提示
                print(f"警告: 未知的 TEXT_READING_DIRECTION '{TEXT_READING_DIRECTION}'，将执行默认拼接。")
                merged_description = desc1 + desc2

            new_shape['description'] = merged_description
        
        elif desc1 and not desc2:
            new_shape['description'] = desc1
        elif desc2 and not desc1:
            new_shape['description'] = desc2
    # ======================== 重构逻辑结束 ========================

    return new_shape

def vertical_can_merge(box1, box2, params):
    eps = params.get("overlap_epsilon", 0.0)
    overlap_x = max(0.0, min(box1[2], box2[2]) - max(box1[0], box2[0]))
    overlap_x_adj = max(0.0, overlap_x + eps)
    width1 = max(0.0, box1[2] - box1[0])
    width2 = max(0.0, box2[2] - box2[0])
    min_width = max(1e-6, min(width1, width2))
    overlap_ratio_w = (overlap_x_adj / min_width) * 100.0
    vertical_gap = max(box1[1], box2[1]) - min(box1[3], box2[3])

    if ADVANCED_MERGE_OPTIONS["debug_mode"]:
        print(f"      垂直判定: overlap_w={overlap_ratio_w:.2f}%, gap={vertical_gap:.3f}")

    if overlap_ratio_w < params["min_width_overlap_ratio"]:
        return False

    if ADVANCED_MERGE_OPTIONS["allow_negative_gap"]:
        return vertical_gap <= params["max_vertical_gap"]
    else:
        return 0 <= vertical_gap <= params["max_vertical_gap"]

def can_merge_shapes(shape1, shape2, mode, params):
    if not can_labels_merge(shape1.get('label', ''), shape2.get('label', '')):
        if ADVANCED_MERGE_OPTIONS["debug_mode"]:
            print(f"    跳过: 标签规则不允许 -> {shape1.get('label','')} vs {shape2.get('label','')}")
        return False

    box1, box2 = get_bounding_box(shape1), get_bounding_box(shape2)

    if mode == "VERTICAL":
        return vertical_can_merge(box1, box2, params)
    else: # 水平模式逻辑 (此处未修改)
        eps = HORIZONTAL_MERGE_PARAMS.get("overlap_epsilon", 0.0)
        overlap_y = max(0.0, min(box1[3], box2[3]) - max(box1[1], box2[1]))
        overlap_y_adj = max(0.0, overlap_y + eps)
        height1 = max(0.0, box1[3] - box1[1])
        height2 = max(0.0, box2[3] - box2[1])
        min_height = max(1e-6, min(height1, height2))
        overlap_ratio_h = (overlap_y_adj / min_height) * 100.0
        horizontal_gap = max(box1[0], box2[0]) - min(box1[2], box2[2])
        if overlap_ratio_h < HORIZONTAL_MERGE_PARAMS["min_height_overlap_ratio"]:
            return False
        if ADVANCED_MERGE_OPTIONS["allow_negative_gap"]:
            return horizontal_gap <= HORIZONTAL_MERGE_PARAMS["max_horizontal_gap"]
        else:
            return 0 <= horizontal_gap <= HORIZONTAL_MERGE_PARAMS["max_horizontal_gap"]

def perform_merge(shapes, mode):
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
                    b1, b2 = get_bounding_box(shape1), get_bounding_box(shape2)
                    merged_box = [min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3])]
                    
                    # <--- 修改: 调用 create_shape_from_box 时不再需要 merge_mode
                    new_shape = create_shape_from_box(merged_box, shape1, shape2)

                    shapes.pop(j)
                    shapes.pop(i)
                    shapes.insert(i, new_shape)
                    merge_count += 1
                    merged_in_pass = True
                    if ADVANCED_MERGE_OPTIONS["debug_mode"]:
                        print(f"    合并: '{shape1.get('label','')}' + '{shape2.get('label','')}' -> '{new_shape.get('label','')}'")
                        print(f"      文本合并: '{shape1.get('description', '')}' + '{shape2.get('description', '')}' -> '{new_shape.get('description', '')}'")
                    break
                else:
                    j += 1
            if merged_in_pass: break
            else: i += 1
        if not merged_in_pass: break
    if merge_count > 0:
        print(f"    {mode} 合并: 执行了 {merge_count} 次合并操作")
    return shapes

def process_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
    except Exception as e:
        print(f"  - 错误: 读取文件 '{os.path.basename(file_path)}' 时失败: {e}"); return False
    if 'shapes' not in data or not data['shapes']:
        print(f"  - 跳过: {os.path.basename(file_path)} (无标注框)"); return False
    initial_shapes = copy.deepcopy(data['shapes'])
    initial_count = len(initial_shapes)
    if MERGE_MODE == "NONE":
        print(f"  - 跳过: {os.path.basename(file_path)} (合并模式为NONE)"); return False
    print(f"  - 处理: {os.path.basename(file_path)} (初始框数: {initial_count})")

    if MERGE_MODE == "VERTICAL":
        final_shapes = perform_merge(initial_shapes, "VERTICAL")
    elif MERGE_MODE == "HORIZONTAL":
        final_shapes = perform_merge(initial_shapes, "HORIZONTAL")
    elif MERGE_MODE == "VERTICAL_THEN_HORIZONTAL":
        temp = perform_merge(initial_shapes, "VERTICAL")
        final_shapes = perform_merge(temp, "HORIZONTAL")
    elif MERGE_MODE == "HORIZONTAL_THEN_VERTICAL":
        temp = perform_merge(initial_shapes, "HORIZONTAL")
        final_shapes = perform_merge(temp, "VERTICAL")
    else: final_shapes = initial_shapes

    data['shapes'] = final_shapes
    try:
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"    完成: 框数 {initial_count} -> {len(final_shapes)} (减少了 {initial_count - len(final_shapes)} 个框)")
        return True
    except Exception as e:
        print(f"  - 错误: 写入文件 '{os.path.basename(file_path)}' 时失败: {e}"); return False

def main():
    print("="*60)
    print("区域合并脚本（支持多种文本阅读方向）")
    print(f"合并模式 (几何): {MERGE_MODE}")
    print(f"文本阅读方向 (内容): {TEXT_READING_DIRECTION}") # <--- 新增
    print(f"合并description文本: {'是' if MERGE_DESCRIPTIONS else '否'}")
    print(f"要求相同标签: {'是' if REQUIRE_SAME_LABEL else '否'}")
    print("="*60 + "\n")

    files_to_process = []
    if len(sys.argv) > 1:
        print("进入 [拖拽模式]...")
        unique_json_paths = set()
        for path in sys.argv[1:]:
            if os.path.isfile(path) and path.lower().endswith('.json'): unique_json_paths.add(os.path.abspath(path))
            elif os.path.isdir(path):
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        if filename.lower().endswith('.json'): unique_json_paths.add(os.path.join(root, filename))
        files_to_process = sorted(list(unique_json_paths))
    else:
        print("进入 [双击模式]...")
        try: work_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError: work_dir = os.getcwd()
        print(f"扫描目录: {work_dir}")
        files_to_process = [os.path.join(work_dir, f) for f in os.listdir(work_dir) if f.lower().endswith('.json')]

    if not files_to_process:
        print("\n未找到任何 .json 文件进行处理。"); input("按 Enter 键退出..."); return
    print(f"\n找到 {len(files_to_process)} 个目标JSON文件，开始处理...\n")
    processed_count = 0
    for file_path in files_to_process:
        if file_path == os.path.abspath(__file__): continue
        if process_file(file_path): processed_count += 1
    print(f"\n处理完成！总共修改了 {processed_count} 个 JSON 文件。")
    input("按 Enter 键退出...")

if __name__ == "__main__":
    main()