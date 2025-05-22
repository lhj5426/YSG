import os
import sys
import json

def update_itp_file(file_path):
    parent_dir = os.path.dirname(file_path)

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    try:
        json_content = json.loads(content)
        json_content['dirPath'] = parent_dir

        # 获取目录下所有 .jpg 文件（不排序，直接写）
        image_files = [f for f in os.listdir(parent_dir) if f.lower().endswith('.jpg')]

        # 直接写入文件名对应的空 boxes
        images_dict = {img: {"boxes": []} for img in image_files}
        json_content['images'] = images_dict

        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(json_content, file, indent=4, ensure_ascii=False)

        print(f'更新成功: {file_path}')
        print(f'图片数量: {len(image_files)}')

    except json.JSONDecodeError:
        print(f'错误: 无法解析 JSON 内容 - {file_path}')
    except Exception as e:
        print(f'错误: {e}')

if __name__ == "__main__":
    for file_path in sys.argv[1:]:
        if file_path.lower().endswith('.itp'):
            update_itp_file(file_path)
