import os
import sys
import cv2
import math
import numpy as np

# ================= 用户可调设置 =================
IMG_EXTS = [".jpg", ".jpeg", ".png", ".bmp"]  # 支持的图片格式

# 旋转后的边界策略：
# - 'constant' -> 常量填充，给你“白边”（不拉伸，尺寸不变）
# - 'replicate' -> 边缘复制（无白边，但会有拉伸感）
# - 'expand' -> 扩大画布以完整容纳旋转图（无白边、不拉伸，尺寸变大）
BORDER_MODE = 'expand'

# 常量填充颜色（B,G,R），仅当 BORDER_MODE == 'constant' 时生效
BORDER_VALUE = (255, 255, 255)
# ===============================================


def rotate_points_affine(points_xy, M):
    pts = np.hstack([points_xy.astype(np.float32), np.ones((len(points_xy), 1), dtype=np.float32)])
    out = (M @ pts.T).T
    return out


def _get_rotation_matrix_expand(w, h, angle_deg):
    """
    计算扩展画布的旋转矩阵与新尺寸，使旋转后完整显示图像。
    返回: M(2x3), (new_w, new_h)
    """
    angle = math.radians(angle_deg)
    cos = abs(math.cos(angle))
    sin = abs(math.sin(angle))

    new_w = int(w * cos + h * sin + 0.5)
    new_h = int(h * cos + w * sin + 0.5)

    # 原图中心 -> 新图中心的平移
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    M[0, 2] += (new_w - w) / 2.0
    M[1, 2] += (new_h - h) / 2.0
    return M, (new_w, new_h)


def rotate_obb_labels(txt_path, save_path, rot_mat, img_size):
    """
    使用与图像相同的仿射矩阵 rot_mat 旋转 YOLO-OBB 标签。
    txt 格式：cls x1 y1 x2 y2 x3 y3 x4 y4（归一化）
    """
    W, H = img_size

    if not os.path.exists(txt_path):
        return

    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 9:
            continue

        cls = parts[0]
        coords_norm = list(map(float, parts[1:9]))

        # 归一化 -> 像素
        pts_pix = []
        for i in range(0, 8, 2):
            x = coords_norm[i] * W
            y = coords_norm[i + 1] * H
            pts_pix.append([x, y])
        pts_pix = np.array(pts_pix, dtype=np.float32)

        # 旋转（与图像同矩阵）
        pts_rot_pix = rotate_points_affine(pts_pix, rot_mat)

        # 拟合最小外接矩形，稳定顶点
        rect = cv2.minAreaRect(pts_rot_pix.astype(np.float32))
        box_pix = cv2.boxPoints(rect)

        # 像素 -> 归一化（夹紧）
        out_W = rot_mat_out_size[0]
        out_H = rot_mat_out_size[1]
        new_coords_norm = []
        for x_p, y_p in box_pix:
            x_norm = float(np.clip(x_p / out_W, 0.0, 1.0))
            y_norm = float(np.clip(y_p / out_H, 0.0, 1.0))
            new_coords_norm.extend([x_norm, y_norm])

        new_line = f"{cls} " + " ".join(f"{v:.8f}" for v in new_coords_norm)
        new_lines.append(new_line)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


def normalize_user_angle(user_input_angle):
    """
    将用户输入转为两个语义：
    - 顺时针为正的角度 cw_angle（0~180 顺时针，>180 表示逆时针 360-a）
    - OpenCV 角度 cv_angle（逆时针为正）
    """
    a = float(user_input_angle) % 360.0
    if 0 <= a <= 180:
        cw_angle = a                      # 顺时针 a
    else:
        cw_angle = -(360.0 - a)           # 例如 350 -> -10（逆时针 10）
    cv_angle = -cw_angle                  # OpenCV 逆时针为正
    return cw_angle, cv_angle


def rotate_image_with_border(img, cv_angle):
    """
    根据全局 BORDER_MODE 处理图像旋转。
    返回: rotated_img, out_size(W,H), rot_mat(2x3)
    """
    h, w = img.shape[:2]

    if BORDER_MODE == 'expand':
        # 扩大画布，避免白边/拉伸，尺寸变化
        M, (new_w, new_h) = _get_rotation_matrix_expand(w, h, cv_angle)
        rotated = cv2.warpAffine(img, M, (new_w, new_h),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=BORDER_VALUE)
        return rotated, (new_w, new_h), M

    # 尺寸不变两种：constant（白边）/ replicate（拉伸）
    center = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(center, cv_angle, 1.0)

    if BORDER_MODE == 'constant':
        rotated = cv2.warpAffine(img, M, (w, h),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=BORDER_VALUE)
    else:  # 'replicate'
        rotated = cv2.warpAffine(img, M, (w, h),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REPLICATE)

    return rotated, (w, h), M


def process_folder(folder_path, user_input_angle):
    """
    处理文件夹中的所有图片和标签。
    """
    cw_angle, cv_angle_to_use = normalize_user_angle(user_input_angle)

    print(f"用户输入: {user_input_angle}°")
    print(f"解释为顺时针角度: {cw_angle}°（正=顺时针，负=逆时针）")
    print(f"用于 OpenCV 的角度: {cv_angle_to_use}°（逆时针为正）")
    print(f"BORDER_MODE: {BORDER_MODE}")

    angle_str = str(user_input_angle).rstrip("0").rstrip(".") if "." in str(user_input_angle) else str(user_input_angle)
    out_dir = os.path.join(folder_path, f"{angle_str}du")
    os.makedirs(out_dir, exist_ok=True)

    files = os.listdir(folder_path)
    img_files = [f for f in files if os.path.splitext(f)[1].lower() in IMG_EXTS]

    if not img_files:
        print("未找到图片文件。")
        return

    global rot_mat_out_size  # 让标签函数知道输出尺寸
    for img_name in img_files:
        img_path = os.path.join(folder_path, img_name)
        name_no_ext = os.path.splitext(img_name)[0]
        txt_path = os.path.join(folder_path, name_no_ext + ".txt")

        img = cv2.imread(img_path)
        if img is None:
            continue

        # 1) 旋转图像（得到 rot_mat 与输出尺寸）
        rotated_img, out_size, rot_mat = rotate_image_with_border(img, cv_angle_to_use)
        rot_mat_out_size = out_size  # (W, H)
        out_W, out_H = out_size
        if rotated_img is None or out_W == 0:
            continue

        # 保存图片
        save_img_path = os.path.join(out_dir, img_name)
        cv2.imwrite(save_img_path, rotated_img)

        # 2) 旋转标签：使用同一 rot_mat 和输出尺寸
        if os.path.exists(txt_path):
            save_txt_path = os.path.join(out_dir, name_no_ext + ".txt")
            rotate_obb_labels(txt_path, save_txt_path, rot_mat, (img.shape[1], img.shape[0]))
        else:
            print(f"⚠️ 未找到对应标签：{txt_path}")

    print(f"\n✅ 处理完成，结果保存在：{out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请将包含图片和TXT的文件夹拖拽到脚本上运行。")
        input("按回车退出...")
        sys.exit()

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print("路径无效，请拖入文件夹。")
        sys.exit()

    try:
        angle = float(input("请输入旋转角度（0到359之间，例如 10=顺时针10°, 350=逆时针10°）："))
        if not (0 <= angle < 360):
            raise ValueError
    except ValueError:
        print("输入无效，请输入0到359之间的数字。")
        input("按回车退出...")
        sys.exit()

    process_folder(folder, angle)
    input("\n处理完毕，按回车退出。")