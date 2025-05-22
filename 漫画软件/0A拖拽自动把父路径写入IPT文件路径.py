import os
import sys
import json

def update_itp_file(file_path):
    # 获取文件的父级目录路径
    parent_dir = os.path.dirname(file_path)

    # 读取 .itp 文件的内容
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    try:
        # 解析 JSON 内容
        json_content = json.loads(content)

        # 更新 dirPath 字段
        json_content['dirPath'] = parent_dir

        # 获取目录下所有 .jpg 文件，按数字排序
        image_files = [f for f in os.listdir(parent_dir) if f.lower().endswith('.jpg')]
        image_files.sort(key=lambda x: int(os.path.splitext(x)[0]))  # 按纯数字排序

        # 构造 images 字段
        images_dict = {img: {"boxes": []} for img in image_files}
        json_content['images'] = images_dict

        # 写入更新后的内容
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
