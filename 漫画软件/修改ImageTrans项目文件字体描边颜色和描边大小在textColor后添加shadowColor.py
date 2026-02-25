import sys
import json
import os

# ========== 自定义设置区 ==========
MODIFY_SHADOW_COLOR = True
SHADOW_COLOR_DARK = "0,0,0,1"  # 浅色文字用的黑色描边
SHADOW_COLOR_LIGHT = "255,255,255,1"  # 深色文字用的白色描边
MODIFY_SHADOW_RADIUS = True
SHADOW_RADIUS_VALUE = 3
# 深色文字亮度阈值（0-255），低于此值认为是深色，使用白色描边
DARK_TEXT_THRESHOLD = 100
# ================================

def is_dark_color(color_str):
    """判断颜色是否为深色
    color_str格式: "R.0,G.0,B.0" 或 "R,G,B"
    """
    try:
        # 解析RGB值
        parts = color_str.split(',')
        r = float(parts[0])
        g = float(parts[1])
        b = float(parts[2])
        
        # 计算亮度 (使用加权平均公式)
        brightness = (r * 0.299 + g * 0.587 + b * 0.114)
        
        # 如果亮度低于阈值，认为是深色
        return brightness < DARK_TEXT_THRESHOLD
    except:
        return False

def insert_or_move_shadowRadius_before_wrappedText(d):
    """在字典中，如果存在wrappedText键，则确保shadowRadius键在wrappedText前面，
    并且shadowRadius的值为SHADOW_RADIUS_VALUE（如果开启修改）。
    如果没有shadowRadius键，则插入一个。"""
    if not isinstance(d, dict):
        return d
    
    if "wrappedText" in d:
        # 先准备新的字典
        new_dict = {}
        inserted_shadowRadius = False
        
        for key in d:
            if key == "wrappedText":
                # 在wrappedText前插入shadowRadius
                if MODIFY_SHADOW_RADIUS:
                    print(f"设置 shadowRadius = {SHADOW_RADIUS_VALUE}，位置在 wrappedText 前")
                    new_dict["shadowRadius"] = SHADOW_RADIUS_VALUE
                else:
                    # 如果不开启修改，且原字典有shadowRadius，保留原值
                    if "shadowRadius" in d:
                        new_dict["shadowRadius"] = d["shadowRadius"]
                new_dict["wrappedText"] = d["wrappedText"]
                inserted_shadowRadius = True
            elif key == "shadowRadius":
                # shadowRadius已经插入过了，跳过这个key
                if inserted_shadowRadius:
                    continue
                else:
                    # 如果wrappedText还没遇到，暂时不插入shadowRadius
                    if MODIFY_SHADOW_RADIUS:
                        print(f"修改 shadowRadius: {d[key]} -> {SHADOW_RADIUS_VALUE}")
                        new_dict["shadowRadius"] = SHADOW_RADIUS_VALUE
                    else:
                        new_dict["shadowRadius"] = d[key]
            else:
                new_dict[key] = d[key]
        
        # 如果wrappedText存在但shadowRadius没插入（wrappedText是最后一个键）
        if "wrappedText" in d and not inserted_shadowRadius:
            if MODIFY_SHADOW_RADIUS:
                print(f"设置 shadowRadius = {SHADOW_RADIUS_VALUE}，位置在 wrappedText 前（wrappedText最后）")
                # 重新构造字典，插入shadowRadius到wrappedText前
                temp_dict = {}
                for key in new_dict:
                    if key == "wrappedText":
                        temp_dict["shadowRadius"] = SHADOW_RADIUS_VALUE
                    temp_dict[key] = new_dict[key]
                new_dict = temp_dict
        
        return new_dict
    else:
        return d

def insert_shadowColor_after_textColor(d):
    """在字典中，如果存在textColor键，则在其后面插入shadowColor键"""
    if not isinstance(d, dict):
        return d
    
    if "textColor" in d:
        # 根据文字颜色选择描边颜色
        is_dark = is_dark_color(d["textColor"])
        shadow_color = SHADOW_COLOR_LIGHT if is_dark else SHADOW_COLOR_DARK
        
        if is_dark:
            print(f"检测到深色文字 textColor={d['textColor']}，使用白色描边")
        
        new_dict = {}
        for key, value in d.items():
            new_dict[key] = value
            # 在textColor后面插入shadowColor
            if key == "textColor":
                if "shadowColor" not in d:
                    print(f"在 textColor 后添加 shadowColor = {shadow_color}")
                    new_dict["shadowColor"] = shadow_color
                elif MODIFY_SHADOW_COLOR:
                    # 如果已存在shadowColor，修改它的值
                    print(f"修改 shadowColor: {d.get('shadowColor')} -> {shadow_color}")
        return new_dict
    else:
        return d

def recursive_modify(obj):
    if isinstance(obj, dict):
        # 先递归修改子元素
        for k in list(obj.keys()):
            obj[k] = recursive_modify(obj[k])
        
        # 根据文字颜色选择描边颜色
        if "textColor" in obj:
            is_dark = is_dark_color(obj["textColor"])
            shadow_color = SHADOW_COLOR_LIGHT if is_dark else SHADOW_COLOR_DARK
            
            # 修改 shadowColor（如果已存在且开启修改）
            if MODIFY_SHADOW_COLOR and "shadowColor" in obj:
                print(f"修改 shadowColor: {obj['shadowColor']} -> {shadow_color}")
                obj["shadowColor"] = shadow_color
        
        # 在textColor后插入shadowColor（函数内部会根据颜色选择描边）
        obj = insert_shadowColor_after_textColor(obj)
        
        # 处理 shadowRadius 和 wrappedText 位置关系
        obj = insert_or_move_shadowRadius_before_wrappedText(obj)
        
        return obj
    elif isinstance(obj, list):
        return [recursive_modify(item) for item in obj]
    else:
        return obj

def process_itp_file(file_path):
    print(f"开始处理文件: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print(f"文件 {file_path} 不是有效的JSON格式，跳过。")
        return
    
    data = recursive_modify(data)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"已完成文件: {file_path}\n")

def main():
    if len(sys.argv) < 2:
        print("请拖拽.ITP文件到此脚本上运行，或在命令行参数中指定文件路径。")
        input("按任意键退出...")
        return
    
    for file_path in sys.argv[1:]:
        if not os.path.isfile(file_path):
            print(f"{file_path} 不是有效文件，跳过。")
            continue
        
        if not file_path.lower().endswith('.itp'):
            print(f"{file_path} 不是.ITP文件，跳过。")
            continue
        
        process_itp_file(file_path)
    
    input("全部处理完成，按任意键退出...")

if __name__ == "__main__":
    main()
