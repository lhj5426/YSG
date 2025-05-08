import sys
import os
import json
import re

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0)

def extract_color_from_rich_text(rich_text):
    """
    从 rich_text 中提取第一个 #RRGGBB 格式的颜色值，忽略大小写和空格。
    返回 (R, G, B) 三元组，找不到时返回 None。
    """
    match = re.search(r'(?i)color\s*:\s*#([0-9a-f]{6})', rich_text)
    if match:
        hex_code = match.group(1)
        return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    return None

def find_itp_file(directory):
    for file in os.listdir(directory):
        if file.endswith('.itp'):
            return os.path.join(directory, file)
    return None

def process_file(input_file, itp_file):
    with open(input_file, encoding='utf-8') as f1:
        data1 = json.load(f1)
    with open(itp_file, encoding='utf-8') as f2:
        data2 = json.load(f2)

    data2['dirPath'] = data1.get('directory', '')

    for page, boxes in data1.get('pages', {}).items():
        data2.setdefault('images', {})[page] = {'boxes': []}

        for box in boxes:
            bounding_rect = box.get('_bounding_rect')
            if not bounding_rect:
                print(f"Warning: '_bounding_rect' missing on page {page}, skip.")
                continue

            x, y, w, h = bounding_rect
            angle = box.get('angle', 0)
            fg_colors = box.get('fg_colors')

            rich_text = box.get('rich_text', '')
            extracted_rgb = extract_color_from_rich_text(rich_text)

            if extracted_rgb:
                textColor = ','.join(map(str, extracted_rgb))
            elif 'fontformat' in box and 'frgb' in box['fontformat']:
                # Extract color from fontformat -> frgb
                textColor = ','.join(map(str, box['fontformat']['frgb']))
            elif fg_colors:
                textColor = ','.join(map(str, map(int, fg_colors)))
            else:
                textColor = '0,0,0'

            # Extract shadow color from srgb if available
            if 'fontformat' in box and 'srgb' in box['fontformat']:
                shadowColor = ','.join(map(str, box['fontformat']['srgb'])) + ',1'
            else:
                shadowColor = '0,0,0,1'  # Default shadow color

            raw_text = box.get('text', '')
            if isinstance(raw_text, list):
                full_text = ''.join(raw_text)
            else:
                full_text = str(raw_text)

            data2['images'][page]['boxes'].append({
                'degree': angle,
                'geometry': {'X': x, 'Y': y, 'width': w, 'height': h},
                'text': full_text,
                'textColor': textColor,
                'shadowColor': shadowColor,
                'target': box.get('translation', '')
            })

    output_file = os.path.splitext(input_file)[0] + '.itp'
    with open(output_file, 'w', encoding='utf-8') as f3:
        json.dump(data2, f3, indent=4, ensure_ascii=False)

    print(f'\n✅ 处理完成：{input_file}\n输出：{output_file}')

if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            print('请将 JSON 文件拖拽到脚本上运行。')
            input("按任意键退出...")
            sys.exit(1)

        for input_file in sys.argv[1:]:
            itp_file = find_itp_file(os.path.dirname(input_file))
            if itp_file:
                process_file(input_file, itp_file)
            else:
                print(f'❌ 未找到 .itp，跳过：{input_file}')
    except Exception as e:
        print(f"\n❌ 处理失败：{e}")
        input("\n按任意键退出...")
