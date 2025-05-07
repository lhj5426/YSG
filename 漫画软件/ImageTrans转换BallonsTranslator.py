import json
import sys
import os

def convert_image_trans_to_ballons_trans(image_trans_data):
    # 读取dirPath
    dir_path = image_trans_data.get("dirPath", "")

    # 读取images数据
    images = image_trans_data.get("images", {})

    # 目标BallonsTranslator结构
    ballons_trans = {
        "directory": dir_path,
        "pages": {},
        "current_img": ""
    }

    for img_name, img_data in images.items():
        boxes = img_data.get("boxes", [])
        page_boxes = []
        for box in boxes:
            geom = box.get("geometry", {})
            style = box.get("localStyle", {})
            # 解析颜色字符串，转换成数组格式
            def parse_color(color_str):
                # 颜色格式可能是 "r,g,b" 或 "r,g,b,a"
                parts = color_str.split(",")
                return [int(float(p)) for p in parts]

            fontcolor = style.get("fontcolor", "0,0,0")
            bgcolor = style.get("bgcolor", "0,0,0")

            # 构造BallonsTranslator的单个box结构
            ballons_box = {
                "xyxy": [
                    geom.get("X", 0),
                    geom.get("Y", 0),
                    geom.get("X", 0) + geom.get("width", 0),
                    geom.get("Y", 0) + geom.get("height", 0)
                ],
                "lines": [
                    [
                        [geom.get("X", 0), geom.get("Y", 0)],
                        [geom.get("X", 0) + geom.get("width", 0), geom.get("Y", 0)],
                        [geom.get("X", 0) + geom.get("width", 0), geom.get("Y", 0) + geom.get("height", 0)],
                        [geom.get("X", 0), geom.get("Y", 0) + geom.get("height", 0)]
                    ]
                ],
                "language": "unknown",
                "distance": [geom.get("height", 0)],  # 这里随便放个高度作为distance示例
                "angle": 0,
                "vec": [0.0, float(geom.get("height", 0))],
                "norm": float(geom.get("height", 0)),
                "merged": False,
                "text": [box.get("text", "")],
                "translation": box.get("target", ""),
                "fontformat": {
                    "font_family": style.get("fontname", ""),
                    "font_size": style.get("size", 20),
                    "stroke_width": 0.2,
                    "frgb": parse_color(bgcolor),
                    "srgb": parse_color(fontcolor),
                    "bold": style.get("bold", False),
                    "underline": False,
                    "italic": style.get("italic", False),
                    "alignment": style.get("alignment", 0),
                    "vertical": False,
                    "font_weight": 400,
                    "line_spacing": style.get("line-height", 1.2),
                    "letter_spacing": style.get("kerning", 1.0),
                    "opacity": 1.0,
                    "shadow_radius": style.get("shadowRadius", 0),
                    "shadow_strength": 1.0,
                    "shadow_color": [255, 255, 255],
                    "shadow_offset": [0.0, 0.0],
                    "gradient_enabled": False,
                    "gradient_start_color": [0, 0, 0],
                    "gradient_end_color": [255, 255, 255],
                    "gradient_angle": 0.0,
                    "gradient_size": 1.0,
                    "_style_name": "",
                    "line_spacing_type": 0,
                    "deprecated_attributes": {}
                }
            }
            page_boxes.append(ballons_box)

        ballons_trans["pages"][img_name] = page_boxes
        ballons_trans["current_img"] = img_name

    return ballons_trans

def main():
    if len(sys.argv) < 2:
        print("请拖拽ImageTrans的JSON文件到此脚本上运行")
        return

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"文件不存在: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        image_trans_data = json.load(f)

    ballons_trans_data = convert_image_trans_to_ballons_trans(image_trans_data)

    output_path = os.path.splitext(input_path)[0] + "_converted.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ballons_trans_data, f, ensure_ascii=False, indent=4)

    print(f"转换完成，结果保存到: {output_path}")

if __name__ == "__main__":
    main()
