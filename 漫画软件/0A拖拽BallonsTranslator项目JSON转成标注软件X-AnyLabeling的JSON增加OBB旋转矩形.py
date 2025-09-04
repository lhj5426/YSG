import sys
import os
import json
import math
from pathlib import Path
from PIL import Image

def convert_ballons_to_anylabel(ballons_json_path):
    """
    将 BallonsTranslator 的项目文件转换为多个 X-AnyLabeling 的 .json 标注文件。
    *** 新版本: 支持对带有 "angle" 字段的框进行反向旋转变换，生成精确的旋转框。***
    """
    try:
        base_dir = Path(ballons_json_path).parent
        with open(ballons_json_path, 'r', encoding='utf-8') as f:
            ballons_data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 '{ballons_json_path}'")
        return
    except json.JSONDecodeError:
        print(f"错误：文件 '{ballons_json_path}' 不是有效的JSON格式。")
        return

    pages = ballons_data.get('pages', {})
    if not pages:
        print("未在文件中找到任何 'pages' 数据。")
        return
    
    print(f"开始转换 {len(pages)} 张图片的标注...")

    for img_name, items in pages.items():
        image_path = base_dir / img_name
        if not image_path.exists():
            print(f"  [跳过] 图片不存在：{img_name}")
            continue

        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception as e:
            print(f"  [跳过] 无法打开图片 {img_name}: {e}")
            continue

        shapes = []
        for item in items:
            description = ''.join(item.get('text', []))
            
            # --- 核心改动: 读取角度和几何信息 ---
            angle_deg = item.get('angle', 0)
            
            # BallonsTranslator 格式使用 _bounding_rect 或 xyxy 来定义未旋转的框
            rect = item.get('_bounding_rect') # [x, y, w, h]
            if not rect:
                xyxy = item.get('xyxy') # [x1, y1, x2, y2]
                if xyxy:
                    rect = [xyxy[0], xyxy[1], xyxy[2] - xyxy[0], xyxy[3] - xyxy[1]]

            if not rect:
                print(f"  [警告] 在 {img_name} 中找到无效的几何数据，已跳过。")
                continue

            x, y, w, h = rect
            
            shape_type = "rectangle"
            points = []
            direction = 0.0

            if angle_deg != 0:
                # 这是一个旋转框，需要进行旋转计算
                shape_type = "rotation"
                angle_rad = math.radians(angle_deg)
                direction = angle_rad

                center_x = x + w / 2
                center_y = y + h / 2

                unrotated_points = [
                    (-w / 2, -h / 2), (w / 2, -h / 2),
                    (w / 2, h / 2), (-w / 2, h / 2)
                ]

                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                
                for px, py in unrotated_points:
                    final_x = center_x + (px * cos_a - py * sin_a)
                    final_y = center_y + (px * sin_a + py * cos_a)
                    points.append([final_x, final_y])
            else:
                # 这是一个普通的水平矩形
                shape_type = "rectangle"
                points = [
                    [x, y], [x + w, y],
                    [x + w, y + h], [x, y + h]
                ]

            shape = {
                # BallonsTranslator 没有 label, 这里给一个默认值
                "label": "text_region", 
                "score": None,
                "points": points,
                "group_id": None,
                "description": description,
                "difficult": False,
                "shape_type": shape_type,
                "flags": {},
                "attributes": {},
                "kie_linking": []
            }
            if shape_type == "rotation":
                shape["direction"] = direction

            shapes.append(shape)

        anylabel_data = {
            "version": "3.2.2",
            "flags": {},
            "shapes": shapes,
            "imagePath": img_name,
            "imageData": None,
            "imageHeight": height,
            "imageWidth": width,
            "description": ""
        }

        output_path = base_dir / f"{Path(img_name).stem}.json"
        with open(output_path, 'w', encoding='utf-8') as out_f:
            json.dump(anylabel_data, out_f, ensure_ascii=False, indent=2)
        print(f"  [完成] 生成标注：{output_path.name}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法：请将一个 BallonsTranslator 的项目文件拖到这个脚本上运行。")
        input("按 Enter 键退出...")
        sys.exit(1)
        
    ballons_file = sys.argv[1]
    if not ballons_file.lower().endswith('.json'):
        print("错误：提供的文件不是 .json 文件。")
        input("按 Enter 键退出...")
        sys.exit(1)
        
    convert_ballons_to_anylabel(ballons_file)
    print("\n所有转换已完成！")
    input("按 Enter 键退出...")