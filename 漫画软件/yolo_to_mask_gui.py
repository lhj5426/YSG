#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO + CTD 文字掩膜生成器 - GUI版本
功能: 
- 图片浏览（放大缩小、上一张下一张）
- 实时掩膜预览（蓝色叠加显示）
- 掩膜大小调整
- 批量生成黑白掩膜
"""

import cv2
import numpy as np
import os
import sys
import torch
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import threading
import json

# 进度条弹窗类
class ProgressDialog:
    def __init__(self, parent, title="正在处理..."):
        self.parent = parent
        self.canceled = False
        
        # 创建弹窗
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x160")  # 稍微加宽加高一点
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+{}+{}".format(
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        # 主框架
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 状态文字
        self.status_var = tk.StringVar(value="初始化...")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.pack(pady=(0, 10))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                          maximum=100, length=350)  # 加宽进度条
        self.progress_bar.pack(pady=(0, 10), fill=tk.X)
        
        # 百分比标签
        self.percent_var = tk.StringVar(value="0%")
        self.percent_label = ttk.Label(main_frame, textvariable=self.percent_var)
        self.percent_label.pack(pady=(0, 15))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # 取消按钮 - 加宽并居中
        self.cancel_button = ttk.Button(button_frame, text="取消操作", width=12,
                                       command=self.cancel_operation)
        self.cancel_button.pack(side=tk.RIGHT, expand=True)  # 居中显示
        
        # 关闭按钮（初始隐藏）- 加宽
        self.close_button = ttk.Button(button_frame, text="关闭", width=12,
                                      command=self.close_dialog)
        
        # 禁止关闭窗口（除非取消）
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel_operation)
    
    def update_progress(self, current, total, status_text=""):
        """更新进度"""
        if self.dialog.winfo_exists():
            percent = int((current / total) * 100) if total > 0 else 0
            self.progress_var.set(percent)
            self.percent_var.set(f"{percent}%")
            if status_text:
                self.status_var.set(status_text)
    
    def cancel_operation(self):
        """取消操作"""
        self.canceled = True
        self.status_var.set("正在取消...")
        self.cancel_button.config(state="disabled")
    
    def finish_operation(self, success=True, message="操作完成"):
        """完成操作"""
        if self.dialog.winfo_exists():
            self.status_var.set(message)
            self.cancel_button.pack_forget()
            self.close_button.pack(side=tk.RIGHT)
            if success:
                self.progress_var.set(100)
                self.percent_var.set("100%")
            
            # 3秒后自动关闭
            self.dialog.after(3000, self.close_dialog)
    
    def close_dialog(self):
        """关闭对话框"""
        if self.dialog.winfo_exists():
            self.dialog.destroy()
    
    def is_canceled(self):
        """检查是否被取消"""
        return self.canceled

# 添加BallonsTranslator路径
ballons_path = r"D:\BallonsTranslator\BallonsTranslator"
if ballons_path not in sys.path:
    sys.path.insert(0, ballons_path)

try:
    from modules.textdetector.ctd import CTDModel
except ImportError:
    print("警告: 无法导入BallonsTranslator模块")
    CTDModel = None

# 支持的图片格式
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
CTD_MODEL_PATH = r"D:\BallonsTranslator\BallonsTranslator\data\models\comictextdetector.pt"

def safe_imread(image_path):
    """安全读取图片，支持中文路径"""
    try:
        # 方法1: 尝试直接用cv2读取
        image = cv2.imread(str(image_path))
        if image is not None:
            return image
        
        # 方法2: 使用numpy和PIL绕过路径问题
        print(f"OpenCV读取失败，尝试PIL读取: {image_path}")
        pil_image = Image.open(image_path)
        # 转换为RGB（PIL默认RGB，OpenCV默认BGR）
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        # 转换为numpy数组，然后转BGR（OpenCV格式）
        image_rgb = np.array(pil_image)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        print(f"PIL读取成功: {image_path}")
        return image_bgr
        
    except Exception as e:
        print(f"❌ 所有方法都失败，无法读取: {image_path}")
        print(f"   错误详情: {e}")
        print(f"   文件是否存在: {Path(image_path).exists()}")
        print(f"   文件大小: {Path(image_path).stat().st_size if Path(image_path).exists() else '文件不存在'}")
        return None

class MaskGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("YOLO + CTD 文字掩膜生成器")
        self.root.geometry("1200x800")
        
        # 数据存储
        self.image_files = []
        self.current_index = 0
        self.labels_folder = None
        self.ctd_model = None
        self.current_image = None
        self.current_mask = None
        self.display_image = None
        self.zoom_factor = 1.0
        self.show_mask = False
        self.show_yolo_boxes = False  # 新增：是否显示YOLO框
        self.current_yolo_boxes = []  # 新增：当前图片的YOLO框
        self.mask_size_factor = 1.0
        
        # 内存管理
        self.mask_cache = {}  # 掩膜缓存：{图片名: 掩膜数据}
        self.max_cache_size = 100  # 最大缓存数量（增加到100）
        
        # 已处理图片记录
        self.processed_images = set()  # 记录已经生成过掩膜的图片名称
        
        # 批量操作控制
        self.cancel_batch_operation = False  # 取消批量操作标志
        
        # 方向延伸参数
        self.extend_left = 0
        self.extend_right = 0
        self.extend_top = 0
        self.extend_bottom = 0
        
        # 配置管理
        self.config_file = Path(__file__).parent / "mask_configs.json"
        self.image_configs = {}  # 每张图片的独立配置
        
        self.load_configs()
        
        self.setup_ui()
        self.load_ctd_model()
        
        # 绑定程序退出事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        """设置UI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧图片显示区域
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 图片画布
        canvas_frame = ttk.Frame(left_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='gray90')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=v_scroll.set)
        
        h_scroll = ttk.Scrollbar(left_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.configure(xscrollcommand=h_scroll.set)
        
        # 右侧控制面板
        right_frame = ttk.Frame(main_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)
        
        # 创建滚动画布和滚动条
        canvas_right = tk.Canvas(right_frame, highlightthickness=0)
        scrollbar_right = ttk.Scrollbar(right_frame, orient="vertical", command=canvas_right.yview)
        scrollable_frame = ttk.Frame(canvas_right)
        
        # 配置滚动区域
        def configure_scroll_region(event=None):
            canvas_right.configure(scrollregion=canvas_right.bbox("all"))
            # 更新滚动条可见性
            update_scrollbar_visibility()
        
        def update_scrollbar_visibility():
            """根据内容高度决定是否显示滚动条"""
            try:
                scrollregion = canvas_right.cget("scrollregion").split()
                if len(scrollregion) == 4:
                    total_height = float(scrollregion[3])
                    visible_height = canvas_right.winfo_height()
                    if total_height > visible_height:
                        scrollbar_right.pack(side="right", fill="y")
                    else:
                        scrollbar_right.pack_forget()
            except:
                pass
        
        def configure_canvas_width(event):
            # 确保scrollable_frame宽度与canvas匹配
            canvas_width = event.width
            canvas_right.itemconfig(canvas_window, width=canvas_width)
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        canvas_right.bind("<Configure>", configure_canvas_width)
        
        canvas_window = canvas_right.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas_right.configure(yscrollcommand=scrollbar_right.set)
        
        # 打包滚动组件 - 默认显示滚动条，后续根据内容动态调整
        canvas_right.pack(side="left", fill="both", expand=True)
        scrollbar_right.pack(side="right", fill="y")
        
        # 初始时延迟更新滚动条可见性
        self.root.after(200, update_scrollbar_visibility)
        
        # 绑定鼠标滚轮事件到右侧面板 - 增强版
        def _on_mousewheel_right(event):
            # 检查鼠标是否在右侧面板区域内
            mouse_x = event.x_root
            canvas_x = canvas_right.winfo_rootx()
            canvas_width = canvas_right.winfo_width()
            
            # 只有鼠标在右侧面板范围内才处理滚动
            if canvas_x <= mouse_x <= canvas_x + canvas_width:
                # 检查是否需要滚动（内容是否超出可视区域）
                try:
                    scrollregion = canvas_right.cget("scrollregion").split()
                    if len(scrollregion) == 4:
                        total_height = float(scrollregion[3])
                        visible_height = canvas_right.winfo_height()
                        if total_height > visible_height:
                            canvas_right.yview_scroll(int(-1*(event.delta/120)), "units")
                            return "break"  # 阻止事件继续传播
                except:
                    # 如果scrollregion还未设置，直接尝试滚动
                    canvas_right.yview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"
        
        def bind_mousewheel_recursively(widget):
            """递归绑定鼠标滚轮事件到所有子控件"""
            widget.bind("<MouseWheel>", _on_mousewheel_right)
            for child in widget.winfo_children():
                bind_mousewheel_recursively(child)
        
        # 绑定到主要控件
        canvas_right.bind("<MouseWheel>", _on_mousewheel_right)
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel_right)
        
        # 延迟绑定所有子控件（在UI创建完成后）
        def bind_all_children():
            try:
                bind_mousewheel_recursively(scrollable_frame)
            except:
                pass
        
        # 添加焦点管理
        def on_enter(event):
            """鼠标进入右侧面板时设置焦点"""
            canvas_right.focus_set()
        
        def on_leave(event):
            """鼠标离开右侧面板时恢复主窗口焦点"""
            self.root.focus_set()
        
        canvas_right.bind("<Enter>", on_enter)
        canvas_right.bind("<Leave>", on_leave)
        
        # 支持键盘滚动
        def on_key_scroll(event):
            if event.keysym == "Up":
                canvas_right.yview_scroll(-1, "units")
            elif event.keysym == "Down":
                canvas_right.yview_scroll(1, "units")
            elif event.keysym == "Prior":  # Page Up
                canvas_right.yview_scroll(-5, "units")
            elif event.keysym == "Next":   # Page Down
                canvas_right.yview_scroll(5, "units")
        
        canvas_right.bind("<Key>", on_key_scroll)
        
        # 确保canvas可以接收键盘事件
        canvas_right.configure(takefocus=True)
        
        # 现在所有的控件都添加到scrollable_frame而不是right_frame
        
        # 文件控制
        file_frame = ttk.LabelFrame(scrollable_frame, text="文件控制", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_frame, text="导入Labels文件夹", 
                  command=self.import_labels_folder).pack(fill=tk.X, pady=(0, 5))
        
        self.status_label = ttk.Label(file_frame, text="未导入文件", foreground="gray")
        self.status_label.pack(fill=tk.X)
        
        # 图片导航
        nav_frame = ttk.LabelFrame(scrollable_frame, text="图片导航", padding=10)
        nav_frame.pack(fill=tk.X, pady=(0, 10))
        
        nav_buttons_frame = ttk.Frame(nav_frame)
        nav_buttons_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(nav_buttons_frame, text="上一张", 
                  command=self.prev_image).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(nav_buttons_frame, text="下一张", 
                  command=self.next_image).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        self.image_info_label = ttk.Label(nav_frame, text="0 / 0")
        self.image_info_label.pack(fill=tk.X)
        
        # 显示控制
        display_frame = ttk.LabelFrame(scrollable_frame, text="显示控制", padding=10)
        display_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 缩放控制
        zoom_frame = ttk.Frame(display_frame)
        zoom_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(zoom_frame, text="缩放:").pack(side=tk.LEFT)
        ttk.Button(zoom_frame, text="-", width=3, 
                  command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="+", width=3, 
                  command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="适应", width=6, 
                  command=self.zoom_fit).pack(side=tk.LEFT, padx=2)
        
        self.zoom_label = ttk.Label(zoom_frame, text="100%")
        self.zoom_label.pack(side=tk.RIGHT)
        
        # 掩膜预览
        self.mask_preview_var = tk.BooleanVar()
        ttk.Checkbutton(display_frame, text="显示掩膜预览", 
                       variable=self.mask_preview_var, 
                       command=self.toggle_mask_preview).pack(fill=tk.X, pady=(0, 5))
        
        # YOLO框预览
        self.yolo_preview_var = tk.BooleanVar()
        ttk.Checkbutton(display_frame, text="显示YOLO框", 
                       variable=self.yolo_preview_var, 
                       command=self.toggle_yolo_preview).pack(fill=tk.X, pady=(0, 5))
        
        # 掩膜大小调整
        mask_size_frame = ttk.LabelFrame(scrollable_frame, text="掩膜大小调整", padding=10)
        mask_size_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(mask_size_frame, text="整体大小:").pack(anchor=tk.W)
        self.mask_size_var = tk.DoubleVar(value=1.0)
        self.mask_size_scale = ttk.Scale(mask_size_frame, from_=0.2, to=5.0, 
                                        variable=self.mask_size_var, 
                                        command=self.on_mask_size_change)
        self.mask_size_scale.pack(fill=tk.X, pady=(0, 5))
        
        # 精确数值输入
        size_input_frame = ttk.Frame(mask_size_frame)
        size_input_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.mask_size_label = ttk.Label(size_input_frame, text="100%")
        self.mask_size_label.pack(side=tk.LEFT)
        
        # 预设按钮
        preset_frame = ttk.Frame(mask_size_frame)
        preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(preset_frame, text="150%", width=6,
                  command=lambda: self.set_mask_size(1.5)).pack(side=tk.LEFT, padx=(0, 1))
        ttk.Button(preset_frame, text="200%", width=6,
                  command=lambda: self.set_mask_size(2.0)).pack(side=tk.LEFT, padx=1)
        ttk.Button(preset_frame, text="250%", width=6,
                  command=lambda: self.set_mask_size(2.5)).pack(side=tk.LEFT, padx=1)
        ttk.Button(preset_frame, text="350%", width=6,
                  command=lambda: self.set_mask_size(3.5)).pack(side=tk.LEFT, padx=(1, 0))
        
        preset_frame2 = ttk.Frame(mask_size_frame)
        preset_frame2.pack(fill=tk.X)
        
        ttk.Button(preset_frame2, text="400%", width=6,
                  command=lambda: self.set_mask_size(4.0)).pack(side=tk.LEFT, padx=(0, 1))
        ttk.Button(preset_frame2, text="450%", width=6,
                  command=lambda: self.set_mask_size(4.5)).pack(side=tk.LEFT, padx=1)
        ttk.Button(preset_frame2, text="500%", width=6,
                  command=lambda: self.set_mask_size(5.0)).pack(side=tk.LEFT, padx=1)
        ttk.Button(preset_frame2, text="重置", width=6,
                  command=self.reset_all_adjustments).pack(side=tk.LEFT, padx=(1, 0))
        
        # 方向延伸调整
        extend_frame = ttk.LabelFrame(scrollable_frame, text="方向延伸调整", padding=10)
        extend_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 使用Grid布局精确对齐
        extend_frame.grid_columnconfigure(1, weight=1)  # 滑块列可拉伸
        
        # 顶部延伸
        ttk.Label(extend_frame, text="↑ 上:", width=6).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.extend_top_var = tk.IntVar()
        tk.Scale(extend_frame, from_=0, to=50, variable=self.extend_top_var, 
                 command=self.on_extend_change, orient=tk.HORIZONTAL,
                 length=200).grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.extend_top_label = ttk.Label(extend_frame, text="0", width=4)
        self.extend_top_label.grid(row=0, column=2, sticky="e")
        
        # 底部延伸
        ttk.Label(extend_frame, text="↓ 下:", width=6).grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(3, 0))
        self.extend_bottom_var = tk.IntVar()
        tk.Scale(extend_frame, from_=0, to=50, variable=self.extend_bottom_var, 
                 command=self.on_extend_change, orient=tk.HORIZONTAL,
                 length=200).grid(row=1, column=1, sticky="ew", padx=(0, 5), pady=(3, 0))
        self.extend_bottom_label = ttk.Label(extend_frame, text="0", width=4)
        self.extend_bottom_label.grid(row=1, column=2, sticky="e", pady=(3, 0))
        
        # 左侧延伸
        ttk.Label(extend_frame, text="← 左:", width=6).grid(row=2, column=0, sticky="w", padx=(0, 5), pady=(3, 0))
        self.extend_left_var = tk.IntVar()
        tk.Scale(extend_frame, from_=0, to=50, variable=self.extend_left_var, 
                 command=self.on_extend_change, orient=tk.HORIZONTAL,
                 length=200).grid(row=2, column=1, sticky="ew", padx=(0, 5), pady=(3, 0))
        self.extend_left_label = ttk.Label(extend_frame, text="0", width=4)
        self.extend_left_label.grid(row=2, column=2, sticky="e", pady=(3, 0))
        
        # 右侧延伸
        ttk.Label(extend_frame, text="→ 右:", width=6).grid(row=3, column=0, sticky="w", padx=(0, 5), pady=(3, 0))
        self.extend_right_var = tk.IntVar()
        tk.Scale(extend_frame, from_=0, to=50, variable=self.extend_right_var, 
                 command=self.on_extend_change, orient=tk.HORIZONTAL,
                 length=200).grid(row=3, column=1, sticky="ew", padx=(0, 5), pady=(3, 0))
        self.extend_right_label = ttk.Label(extend_frame, text="0", width=4)
        self.extend_right_label.grid(row=3, column=2, sticky="e", pady=(3, 0))
        
        # 生成控制
        generate_frame = ttk.LabelFrame(scrollable_frame, text="掩膜操作", padding=10)
        generate_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 使用Grid布局创建田字格（2x2）排列
        generate_frame.grid_columnconfigure(0, weight=1)
        generate_frame.grid_columnconfigure(1, weight=1)
        
        # 第一行：生成掩膜预览 | 重新生成本页掩膜
        ttk.Button(generate_frame, text="生成掩膜预览", 
                  command=self.generate_mask_preview).grid(row=0, column=0, sticky="ew", padx=(0, 2), pady=(0, 5))
        ttk.Button(generate_frame, text="重新生成本页掩膜", 
                  command=self.regenerate_current_mask).grid(row=0, column=1, sticky="ew", padx=(2, 0), pady=(0, 5))
        
        # 第二行：保存当前掩膜 | 批量保存所有
        ttk.Button(generate_frame, text="保存当前掩膜", 
                  command=self.save_current_mask).grid(row=1, column=0, sticky="ew", padx=(0, 2), pady=(0, 5))
        ttk.Button(generate_frame, text="批量保存所有", 
                  command=self.save_all_masks).grid(row=1, column=1, sticky="ew", padx=(2, 0), pady=(0, 5))
        
        # 第三行：导出本页掩膜2 | 批量保存掩膜2
        ttk.Button(generate_frame, text="导出本页掩膜2", 
                  command=self.export_current_itmask).grid(row=2, column=0, sticky="ew", padx=(0, 2), pady=(0, 10))
        ttk.Button(generate_frame, text="批量保存掩膜2", 
                  command=self.export_all_itmasks).grid(row=2, column=1, sticky="ew", padx=(2, 0), pady=(0, 10))
        
        # 配置管理
        config_frame = ttk.LabelFrame(scrollable_frame, text="配置管理", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 使用Grid布局创建田字格（2x2）排列
        config_frame.grid_columnconfigure(0, weight=1)
        config_frame.grid_columnconfigure(1, weight=1)
        
        # 第一行：保存当前配置 | 加载当前配置
        ttk.Button(config_frame, text="保存当前配置", width=12,
                  command=self.save_current_config).grid(row=0, column=0, sticky="ew", padx=(0, 2), pady=(0, 5))
        ttk.Button(config_frame, text="加载当前配置", width=12,
                  command=self.load_current_config).grid(row=0, column=1, sticky="ew", padx=(2, 0), pady=(0, 5))
        
        # 第二行：用当前配置批量保存 | 用当前配置批量保存掩膜2
        ttk.Button(config_frame, text="用当前配置批量保存", 
                  command=self.save_all_with_current_config).grid(row=1, column=0, sticky="ew", padx=(0, 2), pady=(0, 5))
        ttk.Button(config_frame, text="用当前配置保存掩膜2", 
                  command=self.save_all_itmask_with_current_config).grid(row=1, column=1, sticky="ew", padx=(2, 0), pady=(0, 5))
        
        # 第三行：清除掩膜显示（跨两列）
        ttk.Button(config_frame, text="清除掩膜显示", 
                  command=self.clear_mask_cache).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        # 进度显示区域 - 固定在右侧面板底部，不随滚动
        progress_frame = ttk.Frame(right_frame)
        progress_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # 进度条
        progress_bar_frame = ttk.Frame(progress_frame)
        progress_bar_frame.pack(fill=tk.X, pady=(0, 2))
        
        self.progress_bar = ttk.Progressbar(progress_bar_frame, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # 取消按钮（初始隐藏）
        self.cancel_button = ttk.Button(progress_bar_frame, text="取消", width=6,
                                       command=self.cancel_batch_operation_func)
        # 初始不显示取消按钮
        
        # 进度文字
        self.progress_var = tk.StringVar(value="就绪")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        self.progress_label.pack(fill=tk.X)
        
        # 绑定事件
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        # 左侧画布的滚轮缩放事件
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux
        self.root.bind("<Left>", lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())
        self.root.bind("<a>", lambda e: self.prev_image())
        self.root.bind("<A>", lambda e: self.prev_image())
        self.root.bind("<d>", lambda e: self.next_image())
        self.root.bind("<D>", lambda e: self.next_image())
        self.root.focus_set()
        
        # 延迟绑定右侧面板的所有子控件滚轮事件
        self.root.after(100, bind_all_children)
    
    def load_ctd_model(self):
        """加载CTD模型"""
        def load_model():
            try:
                if CTDModel is None:
                    raise ImportError("CTDModel未导入")
                
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self.progress_var.set(f"加载CTD模型 ({device})...")
                self.ctd_model = CTDModel(CTD_MODEL_PATH, detect_size=1024, device=device)
                self.progress_var.set(f"CTD模型加载完成 ({device})")
                
            except Exception as e:
                self.progress_var.set(f"模型加载失败: {str(e)}")
                messagebox.showerror("错误", f"CTD模型加载失败:\n{str(e)}")
        
        # 在后台线程加载模型
        threading.Thread(target=load_model, daemon=True).start()
    
    def import_labels_folder(self):
        """导入labels文件夹"""
        folder = filedialog.askdirectory(title="选择Labels文件夹")
        if not folder:
            return
        
        self.labels_folder = Path(folder)
        # 在labels文件夹的父目录查找图片文件
        image_search_dir = self.labels_folder.parent
        
        # 查找图片文件
        self.image_files = []
        for ext in IMAGE_EXTENSIONS:
            self.image_files.extend(image_search_dir.glob(f"*{ext}"))
        
        # 只保留有对应标签文件的图片
        valid_images = []
        for img_path in self.image_files:
            label_path = self.labels_folder / (img_path.stem + ".txt")
            if label_path.exists():
                valid_images.append(img_path)
        
        self.image_files = valid_images
        
        if self.image_files:
            self.current_index = 0
            self.status_label.config(text=f"找到 {len(self.image_files)} 张图片", foreground="green")
            self.load_current_image()
        else:
            self.status_label.config(text="未找到匹配的图片文件", foreground="red")
            messagebox.showwarning("警告", f"在 {image_search_dir} 中未找到与标签文件匹配的图片文件\n请确保图片文件与labels文件夹在同一目录下")
    
    def clear_mask_cache(self):
        """清除掩膜显示并清理缓存（保留YOLO框）"""
        # 清理缓存和已处理记录
        self.mask_cache.clear()
        self.processed_images.clear()  # 清除已处理记录
        
        # 清除当前掩膜（但保留YOLO框用于指导）
        self.current_mask = None
        # self.current_yolo_boxes = []  # 不清除YOLO框，用于掩膜生成指导
        
        # 重置进度条
        self.progress_bar['value'] = 0
        
        # 立即更新显示（移除蓝色掩膜，保留红色YOLO框）
        self.update_display()
        
        self.progress_var.set("✅ 已清除所有掩膜显示和记录（YOLO框保留用于指导）")
    
    def manage_mask_cache(self, image_name, mask):
        """管理掩膜缓存，防止内存溢出"""
        # 如果缓存已满，删除最旧的缓存
        if len(self.mask_cache) >= self.max_cache_size:
            # 删除第一个（最旧的）缓存
            oldest_key = next(iter(self.mask_cache))
            del self.mask_cache[oldest_key]
        
        # 添加新缓存
        self.mask_cache[image_name] = mask.copy() if mask is not None else None
    
    def get_cached_mask(self, image_name):
        """获取缓存的掩膜"""
        return self.mask_cache.get(image_name, None)
    
    def load_yolo_boxes_for_current_image(self):
        """只加载YOLO框数据，不生成掩膜"""
        if not self.image_files:
            return
        
        try:
            image_path = self.image_files[self.current_index]
            label_path = self.labels_folder / (image_path.stem + ".txt")
            
            # 读取YOLO标签
            boxes = self.read_yolo_labels(str(label_path))
            yolo_boxes = self.yolo_to_pixel_coords(boxes, 
                                                 self.current_image.shape[1], 
                                                 self.current_image.shape[0]) if boxes else []
            
            # 保存YOLO框用于显示
            self.current_yolo_boxes = yolo_boxes
                
        except Exception as e:
            print(f"加载YOLO框错误: {e}")
            self.current_yolo_boxes = []
    
    def generate_mask_for_current_image(self):
        """为当前图片生成掩膜"""
        if not self.image_files or self.ctd_model is None:
            return
        
        try:
            image_path = self.image_files[self.current_index]
            image_name = image_path.stem
            
            # 首先检查缓存
            cached_mask = self.get_cached_mask(image_name)
            if cached_mask is not None:
                self.current_mask = cached_mask
                self.progress_var.set(f"✅ 从缓存加载掩膜: {image_name}")
                return
            
            # 如果YOLO框数据为空，重新加载
            if not self.current_yolo_boxes:
                self.load_yolo_boxes_for_current_image()
            
            # 使用自定义阈值的CTD生成掩膜
            image_bgr = cv2.cvtColor(self.current_image, cv2.COLOR_RGB2BGR)
            mask, mask_refined = self.generate_ctd_mask_with_thresh(image_bgr)
            
            # YOLO过滤
            if self.current_yolo_boxes:
                self.current_mask = self.filter_mask_with_yolo_boxes(mask_refined, self.current_yolo_boxes)
            else:
                self.current_mask = mask_refined
            
            # 缓存掩膜
            self.manage_mask_cache(image_name, self.current_mask)
            self.progress_var.set(f"✅ 生成并缓存掩膜: {image_name} (缓存: {len(self.mask_cache)}/{self.max_cache_size})")
                
        except Exception as e:
            print(f"生成掩膜错误: {e}")
            self.current_mask = np.zeros((self.current_image.shape[0], self.current_image.shape[1]), dtype=np.uint8)
            self.current_yolo_boxes = []
    
    def generate_ctd_mask_with_thresh(self, image_bgr):
        """使用默认阈值生成CTD掩膜"""
        try:
            # 直接使用CTD模型的默认设置，简化处理
            mask, mask_refined, blk_list = self.ctd_model(image_bgr, refine_mode=0, keep_undetected_mask=False)
            return mask, mask_refined
            
        except Exception as e:
            print(f"CTD处理失败: {e}")
            # 回退到空掩膜
            h, w = image_bgr.shape[:2]
            empty_mask = np.zeros((h, w), dtype=np.uint8)
            return empty_mask, empty_mask
    
    def read_yolo_labels(self, label_path):
        """读取YOLO标签"""
        boxes = []
        try:
            with open(label_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        _, x_center, y_center, width, height = map(float, parts[:5])
                        boxes.append((x_center, y_center, width, height))
        except:
            pass
        return boxes
    
    def yolo_to_pixel_coords(self, boxes, img_width, img_height):
        """YOLO坐标转像素坐标"""
        pixel_boxes = []
        for x_center, y_center, width, height in boxes:
            x_center_px = x_center * img_width
            y_center_px = y_center * img_height
            width_px = width * img_width
            height_px = height * img_height
            
            x1 = int(x_center_px - width_px / 2)
            y1 = int(y_center_px - height_px / 2)
            x2 = int(x_center_px + width_px / 2)
            y2 = int(y_center_px + height_px / 2)
            
            x1 = max(0, min(x1, img_width))
            y1 = max(0, min(y1, img_height))
            x2 = max(0, min(x2, img_width))
            y2 = max(0, min(y2, img_height))
            
            pixel_boxes.append((x1, y1, x2, y2))
        return pixel_boxes
    
    def filter_mask_with_yolo_boxes(self, mask, yolo_boxes):
        """用YOLO框过滤掩膜"""
        if not yolo_boxes:
            return mask
        
        yolo_mask = np.zeros_like(mask)
        for x1, y1, x2, y2 in yolo_boxes:
            yolo_mask[y1:y2, x1:x2] = 255
        
        return cv2.bitwise_and(mask, yolo_mask)
    
    def adjust_mask_size(self, mask, factor):
        """调整掩膜大小"""
        if factor == 1.0 and self.extend_left == 0 and self.extend_right == 0 and self.extend_top == 0 and self.extend_bottom == 0:
            return mask
        
        # 先应用整体大小调整
        adjusted_mask = mask
        if factor != 1.0:
            if factor > 1.0:
                # 膨胀
                kernel_size = int((factor - 1.0) * 10) + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                adjusted_mask = cv2.dilate(adjusted_mask, kernel, iterations=1)
            else:
                # 腐蚀
                kernel_size = int((1.0 - factor) * 10) + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                adjusted_mask = cv2.erode(adjusted_mask, kernel, iterations=1)
        
        # 应用方向延伸
        if self.extend_left > 0 or self.extend_right > 0 or self.extend_top > 0 or self.extend_bottom > 0:
            adjusted_mask = self.apply_directional_extensions(adjusted_mask)
        
        return adjusted_mask
    
    def apply_directional_extensions(self, mask):
        """应用单方向延伸 - 4个方向独立单向生长"""
        if (self.extend_left == 0 and self.extend_right == 0 and 
            self.extend_top == 0 and self.extend_bottom == 0):
            return mask
        
        h, w = mask.shape
        result_mask = mask.copy()
        
        # 向上单向延伸
        if self.extend_top > 0:
            for i in range(1, int(self.extend_top) + 1):
                shifted = np.zeros_like(mask)
                if i < h:
                    shifted[:-i, :] = mask[i:, :]
                    result_mask = np.maximum(result_mask, shifted)
        
        # 向下单向延伸
        if self.extend_bottom > 0:
            for i in range(1, int(self.extend_bottom) + 1):
                shifted = np.zeros_like(mask)
                if i < h:
                    shifted[i:, :] = mask[:-i, :]
                    result_mask = np.maximum(result_mask, shifted)
        
        # 向左单向延伸
        if self.extend_left > 0:
            for i in range(1, int(self.extend_left) + 1):
                shifted = np.zeros_like(mask)
                if i < w:
                    shifted[:, :-i] = mask[:, i:]
                    result_mask = np.maximum(result_mask, shifted)
        
        # 向右单向延伸
        if self.extend_right > 0:
            for i in range(1, int(self.extend_right) + 1):
                shifted = np.zeros_like(mask)
                if i < w:
                    shifted[:, i:] = mask[:, :-i]
                    result_mask = np.maximum(result_mask, shifted)
        
        return result_mask
    
    def update_display(self):
        """更新图片显示"""
        if self.current_image is None:
            return
        
        # 获取调整后的掩膜
        display_mask = self.current_mask
        if self.current_mask is not None:
            display_mask = self.adjust_mask_size(self.current_mask, self.mask_size_factor)
        
        # 创建显示图片
        display_img = self.current_image.copy()
        
        # 叠加蓝色掩膜
        if self.show_mask and display_mask is not None:
            # 创建蓝色掩膜
            blue_mask = np.zeros_like(display_img)
            blue_mask[display_mask > 127] = [0, 100, 255]  # 蓝色
            
            # 半透明叠加
            alpha = 0.4
            display_img = cv2.addWeighted(display_img, 1-alpha, blue_mask, alpha, 0)
        
        # 转换为PIL格式
        pil_img = Image.fromarray(display_img)
        
        # 绘制YOLO框
        if self.show_yolo_boxes and self.current_yolo_boxes:
            draw = ImageDraw.Draw(pil_img)
            for x1, y1, x2, y2 in self.current_yolo_boxes:
                # 绘制红色矩形框，线宽2
                draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=2)
        
        # 缩放
        if self.zoom_factor != 1.0:
            new_size = (int(pil_img.width * self.zoom_factor), 
                       int(pil_img.height * self.zoom_factor))
            pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 更新画布
        self.display_image = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.display_image)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def prev_image(self):
        """上一张图片"""
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()
    
    def next_image(self):
        """下一张图片"""
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()
    
    def zoom_in(self):
        """放大"""
        self.zoom_factor = min(self.zoom_factor * 1.2, 5.0)
        self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        self.update_display()
    
    def zoom_out(self):
        """缩小"""
        self.zoom_factor = max(self.zoom_factor / 1.2, 0.1)
        self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        self.update_display()
    
    def zoom_fit(self):
        """适应窗口"""
        if self.current_image is None:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        img_width = self.current_image.shape[1]
        img_height = self.current_image.shape[0]
        
        if canvas_width > 1 and canvas_height > 1:  # 确保画布已初始化
            zoom_x = canvas_width / img_width
            zoom_y = canvas_height / img_height
            self.zoom_factor = min(zoom_x, zoom_y) * 0.9  # 留点边距
            self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
            self.update_display()
    
    def toggle_mask_preview(self):
        """切换掩膜预览"""
        self.show_mask = self.mask_preview_var.get()
        self.update_display()
    
    def toggle_yolo_preview(self):
        """切换YOLO框预览"""
        self.show_yolo_boxes = self.yolo_preview_var.get()
        self.update_display()
    
    def on_mask_size_change(self, value):
        """掩膜大小改变"""
        self.mask_size_factor = float(value)
        self.mask_size_label.config(text=f"{int(self.mask_size_factor * 100)}%")
        
        # 立即更新显示
        if self.show_mask:
            self.update_display()
    
    def generate_current_mask(self):
        """生成当前掩膜文件"""
        if self.current_mask is None:
            self.progress_var.set("警告: 没有可用的掩膜")
            return
        
        try:
            # 获取调整后的掩膜
            final_mask = self.adjust_mask_size(self.current_mask, self.mask_size_factor)
            
            # 保存路径
            image_path = self.image_files[self.current_index]
            mask_dir = Path(__file__).parent / "MASK"
            mask_dir.mkdir(exist_ok=True)
            output_path = mask_dir / (image_path.stem + ".png")
            
            cv2.imwrite(str(output_path), final_mask)
            self.progress_var.set(f"✅ 掩膜已保存: {image_path.stem}.png")
            
        except Exception as e:
            self.progress_var.set(f"❌ 保存掩膜失败: {str(e)}")
    
    def generate_all_masks(self):
        """批量生成所有掩膜"""
        if not self.image_files:
            self.progress_var.set("警告: 没有可处理的图片")
            return
        
        def generate_batch():
            try:
                mask_dir = Path(__file__).parent / "MASK"
                mask_dir.mkdir(exist_ok=True)
                
                success_count = 0
                for i, image_path in enumerate(self.image_files):
                    self.progress_var.set(f"生成掩膜 {i+1}/{len(self.image_files)}")
                    
                    # 临时加载图片
                    temp_image = safe_imread(image_path)
                    if temp_image is None:
                        self.progress_var.set(f"❌ 跳过无法读取的图片: {image_path.name}")
                        continue
                    
                    # 读取标签
                    label_path = self.labels_folder / (image_path.stem + ".txt")
                    boxes = self.read_yolo_labels(str(label_path))
                    yolo_boxes = self.yolo_to_pixel_coords(boxes, 
                                                         temp_image.shape[1], 
                                                         temp_image.shape[0]) if boxes else []
                    
                    # 生成掩膜
                    mask, mask_refined, _ = self.ctd_model(temp_image, refine_mode=0, keep_undetected_mask=False)
                    
                    if yolo_boxes:
                        final_mask = self.filter_mask_with_yolo_boxes(mask_refined, yolo_boxes)
                    else:
                        final_mask = mask_refined
                    
                    # 调整大小
                    final_mask = self.adjust_mask_size(final_mask, self.mask_size_factor)
                    
                    # 保存
                    output_path = mask_dir / (image_path.stem + ".png")
                    cv2.imwrite(str(output_path), final_mask)
                    success_count += 1
                
                self.progress_var.set(f"✅ 批量生成完成: {success_count}/{len(self.image_files)} 张掩膜已生成")
                
            except Exception as e:
                self.progress_var.set(f"❌ 批量生成失败: {str(e)}")
        
        # 在后台线程执行
        threading.Thread(target=generate_batch, daemon=True).start()
    
    def on_canvas_click(self, event):
        """画布点击事件"""
        self.canvas.focus_set()
    
    def on_mouse_wheel(self, event):
        """鼠标滚轮缩放"""
        if self.current_image is None:
            return
        
        # 获取滚轮方向
        if event.delta > 0 or event.num == 4:  # 向上滚动，放大
            self.zoom_factor = min(self.zoom_factor * 1.1, 5.0)
        elif event.delta < 0 or event.num == 5:  # 向下滚动，缩小
            self.zoom_factor = max(self.zoom_factor / 1.1, 0.1)
        
        # 更新缩放标签和显示
        self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        self.update_display()
    
    def set_mask_size(self, size):
        """设置掩膜大小"""
        self.mask_size_var.set(size)
        self.mask_size_factor = size
        self.mask_size_label.config(text=f"{int(size * 100)}%")
        if self.show_mask:
            self.update_display()
    
    def on_extend_change(self, value):
        """方向延伸值改变"""
        self.extend_left = self.extend_left_var.get()
        self.extend_right = self.extend_right_var.get()
        self.extend_top = self.extend_top_var.get()
        self.extend_bottom = self.extend_bottom_var.get()
        
        # 更新标签显示
        self.extend_left_label.config(text=str(self.extend_left))
        self.extend_right_label.config(text=str(self.extend_right))
        self.extend_top_label.config(text=str(self.extend_top))
        self.extend_bottom_label.config(text=str(self.extend_bottom))
        
        # 立即更新显示
        if self.show_mask:
            self.update_display()
    
    def reset_all_adjustments(self):
        """重置所有调整参数"""
        # 重置掩膜大小
        self.mask_size_var.set(1.0)
        self.mask_size_factor = 1.0
        self.mask_size_label.config(text="100%")
        
        # 重置方向延伸
        self.extend_left_var.set(0)
        self.extend_right_var.set(0)
        self.extend_top_var.set(0)
        self.extend_bottom_var.set(0)
        
        self.extend_left = 0
        self.extend_right = 0
        self.extend_top = 0
        self.extend_bottom = 0
        
        # 更新标签显示
        self.extend_left_label.config(text="0")
        self.extend_right_label.config(text="0")
        self.extend_top_label.config(text="0")
        self.extend_bottom_label.config(text="0")
        
        # 更新显示
        if self.show_mask:
            self.update_display()
    
    def generate_mask_preview(self):
        """生成所有页面的掩膜并预览当前页"""
        if not self.image_files or self.ctd_model is None:
            messagebox.showwarning("警告", "请先导入图片和确保模型已加载")
            return
        
        # 创建进度条弹窗
        progress_dialog = ProgressDialog(self.root, "生成所有掩膜")
        
        def generate_all():
            try:
                total_count = len(self.image_files)
                success_count = 0
                
                for i, image_path in enumerate(self.image_files):
                    # 检查是否取消
                    if progress_dialog.is_canceled():
                        progress_dialog.finish_operation(False, "用户取消了操作")
                        return
                    
                    # 更新进度
                    progress_dialog.update_progress(i+1, total_count, 
                                                   f"正在处理: {image_path.name} ({i+1}/{total_count})")
                    
                    image_name = image_path.stem
                    
                    # 检查是否已经有缓存
                    if self.get_cached_mask(image_name) is not None:
                        success_count += 1
                        continue
                    
                    # 临时加载图片
                    temp_image = safe_imread(image_path)
                    if temp_image is None:
                        continue
                    
                    # 读取标签
                    label_path = self.labels_folder / (image_path.stem + ".txt")
                    boxes = self.read_yolo_labels(str(label_path))
                    yolo_boxes = self.yolo_to_pixel_coords(boxes, 
                                                         temp_image.shape[1], 
                                                         temp_image.shape[0]) if boxes else []
                    
                    # 生成掩膜
                    image_bgr = cv2.cvtColor(temp_image, cv2.COLOR_RGB2BGR)
                    mask, mask_refined = self.generate_ctd_mask_with_thresh(image_bgr)
                    
                    # YOLO过滤
                    if yolo_boxes:
                        final_mask = self.filter_mask_with_yolo_boxes(mask_refined, yolo_boxes)
                    else:
                        final_mask = mask_refined
                    
                    # 缓存掩膜并记录已处理
                    self.manage_mask_cache(image_name, final_mask)
                    self.processed_images.add(image_name)  # 记录已处理
                    success_count += 1
                
                # 更新当前页掩膜
                current_image_name = self.image_files[self.current_index].stem
                cached_mask = self.get_cached_mask(current_image_name)
                if cached_mask is not None:
                    self.current_mask = cached_mask
                
                # 完成操作
                self.root.after(0, lambda: (
                    # 自动开启掩膜预览
                    self.mask_preview_var.set(True),
                    setattr(self, 'show_mask', True),
                    # 更新显示
                    self.update_display()
                ))
                
                progress_dialog.finish_operation(True, f"✅ 所有掩膜生成完成: {success_count}/{total_count} 张")
                
            except Exception as e:
                progress_dialog.finish_operation(False, f"❌ 掩膜生成失败: {str(e)}")
        
        # 在后台线程执行
        threading.Thread(target=generate_all, daemon=True).start()
    
    def save_current_mask(self):
        """保存当前掩膜文件（黑白PNG）"""
        if self.current_mask is None:
            self.progress_var.set("警告: 没有可用的掩膜，请先生成掩膜预览")
            return
        
        try:
            # 获取调整后的掩膜
            final_mask = self.adjust_mask_size(self.current_mask, self.mask_size_factor)
            
            # 保存路径
            image_path = self.image_files[self.current_index]
            mask_dir = Path(__file__).parent / "MASK"
            mask_dir.mkdir(exist_ok=True)
            output_path = mask_dir / (image_path.stem + ".png")
            
            cv2.imwrite(str(output_path), final_mask)
            self.progress_var.set(f"✅ 掩膜已保存: {image_path.stem}.png")
            
        except Exception as e:
            self.progress_var.set(f"❌ 保存掩膜失败: {str(e)}")
    
    def save_all_masks(self):
        """批量保存所有掩膜"""
        if not self.image_files:
            messagebox.showwarning("警告", "没有可处理的图片")
            return
        
        # 创建进度条弹窗
        progress_dialog = ProgressDialog(self.root, "批量保存掩膜")
        
        def save_batch():
            try:
                mask_dir = Path(__file__).parent / "MASK"
                mask_dir.mkdir(exist_ok=True)
                
                total_count = len(self.image_files)
                success_count = 0
                
                for i, image_path in enumerate(self.image_files):
                    # 检查是否取消
                    if progress_dialog.is_canceled():
                        progress_dialog.finish_operation(False, "用户取消了操作")
                        return
                    
                    # 更新进度
                    progress_dialog.update_progress(i+1, total_count, 
                                                   f"正在处理: {image_path.name} ({i+1}/{total_count})")
                    
                    # 临时加载图片
                    temp_image = safe_imread(image_path)
                    if temp_image is None:
                        continue
                    
                    # 读取标签
                    label_path = self.labels_folder / (image_path.stem + ".txt")
                    boxes = self.read_yolo_labels(str(label_path))
                    yolo_boxes = self.yolo_to_pixel_coords(boxes, 
                                                         temp_image.shape[1], 
                                                         temp_image.shape[0]) if boxes else []
                    
                    # 生成掩膜
                    mask, mask_refined, _ = self.ctd_model(temp_image, refine_mode=0, keep_undetected_mask=False)
                    
                    if yolo_boxes:
                        final_mask = self.filter_mask_with_yolo_boxes(mask_refined, yolo_boxes)
                    else:
                        final_mask = mask_refined
                    
                    # 调整大小
                    final_mask = self.adjust_mask_size(final_mask, self.mask_size_factor)
                    
                    # 保存
                    output_path = mask_dir / (image_path.stem + ".png")
                    cv2.imwrite(str(output_path), final_mask)
                    success_count += 1
                
                progress_dialog.finish_operation(True, f"✅ 批量保存完成: {success_count}/{total_count} 张掩膜已保存")
                
            except Exception as e:
                progress_dialog.finish_operation(False, f"❌ 批量保存失败: {str(e)}")
        
        # 在后台线程执行
        threading.Thread(target=save_batch, daemon=True).start()
    
    def regenerate_current_mask(self):
        """重新生成当前图片的掩膜"""
        if not self.image_files or self.ctd_model is None:
            messagebox.showwarning("警告", "请先导入图片和确保模型已加载")
            return
        
        try:
            self.progress_var.set("重新生成掩膜中...")
            self.generate_mask_for_current_image()
            
            # 如果开启了预览，更新显示
            if self.show_mask:
                self.update_display()
            
            self.progress_var.set("掩膜重新生成完成")
            
        except Exception as e:
            self.progress_var.set("掩膜生成失败")
            messagebox.showerror("错误", f"重新生成掩膜失败:\n{str(e)}")
    
    def get_current_config(self):
        """获取当前配置"""
        return {
            'mask_size_factor': self.mask_size_factor,
            'extend_left': self.extend_left,
            'extend_right': self.extend_right,
            'extend_top': self.extend_top,
            'extend_bottom': self.extend_bottom
        }
    
    def apply_config(self, config):
        """应用配置"""
        self.mask_size_factor = config.get('mask_size_factor', 1.0)
        self.extend_left = config.get('extend_left', 0)
        self.extend_right = config.get('extend_right', 0)
        self.extend_top = config.get('extend_top', 0)
        self.extend_bottom = config.get('extend_bottom', 0)
        
        # 更新UI控件
        self.mask_size_var.set(self.mask_size_factor)
        self.mask_size_label.config(text=f"{int(self.mask_size_factor * 100)}%")
        
        self.extend_left_var.set(self.extend_left)
        self.extend_right_var.set(self.extend_right)
        self.extend_top_var.set(self.extend_top)
        self.extend_bottom_var.set(self.extend_bottom)
        
        self.extend_left_label.config(text=str(self.extend_left))
        self.extend_right_label.config(text=str(self.extend_right))
        self.extend_top_label.config(text=str(self.extend_top))
        self.extend_bottom_label.config(text=str(self.extend_bottom))
        
        # 不自动重新生成掩膜，让用户手动控制
        # 只更新显示（如果有现有掩膜的话）
        if self.show_mask:
            self.update_display()
    
    def save_current_config(self):
        """保存当前图片的配置"""
        if not self.image_files:
            self.progress_var.set("没有图片可保存配置")
            return
        
        current_image_name = self.image_files[self.current_index].stem
        config = self.get_current_config()
        self.image_configs[current_image_name] = config
        self.save_configs()
        
        self.progress_var.set(f"✅ 已保存 {current_image_name} 的配置")
    
    def load_current_config(self):
        """加载当前图片的配置"""
        if not self.image_files:
            self.progress_var.set("没有图片可加载配置")
            return
        
        current_image_name = self.image_files[self.current_index].stem
        if current_image_name in self.image_configs:
            config = self.image_configs[current_image_name]
            self.apply_config(config)
            self.progress_var.set(f"✅ 已加载 {current_image_name} 的配置")
        else:
            self.progress_var.set(f"❌ {current_image_name} 没有保存的配置")
    
    def save_all_with_current_config(self):
        """用当前配置批量保存所有掩膜"""
        if not self.image_files:
            messagebox.showwarning("警告", "没有可处理的图片")
            return
        
        current_config = self.get_current_config()
        
        # 创建进度条弹窗
        progress_dialog = ProgressDialog(self.root, "用当前配置保存")
        
        def save_batch():
            try:
                mask_dir = Path(__file__).parent / "MASK"
                mask_dir.mkdir(exist_ok=True)
                
                total_count = len(self.image_files)
                success_count = 0
                
                for i, image_path in enumerate(self.image_files):
                    # 检查是否取消
                    if progress_dialog.is_canceled():
                        progress_dialog.finish_operation(False, "用户取消了操作")
                        return
                    
                    # 更新进度
                    progress_dialog.update_progress(i+1, total_count, 
                                                   f"正在处理: {image_path.name} ({i+1}/{total_count})")
                    
                    # 临时加载图片
                    temp_image = safe_imread(image_path)
                    if temp_image is None:
                        continue
                    
                    # 读取标签
                    label_path = self.labels_folder / (image_path.stem + ".txt")
                    boxes = self.read_yolo_labels(str(label_path))
                    yolo_boxes = self.yolo_to_pixel_coords(boxes, 
                                                         temp_image.shape[1], 
                                                         temp_image.shape[0]) if boxes else []
                    
                    # 生成掩膜
                    mask, mask_refined, _ = self.ctd_model(temp_image, refine_mode=0, keep_undetected_mask=False)
                    
                    if yolo_boxes:
                        final_mask = self.filter_mask_with_yolo_boxes(mask_refined, yolo_boxes)
                    else:
                        final_mask = mask_refined
                    
                    # 使用当前配置调整大小
                    final_mask = self.adjust_mask_with_config(final_mask, current_config)
                    
                    # 保存
                    output_path = mask_dir / (image_path.stem + ".png")
                    cv2.imwrite(str(output_path), final_mask)
                    success_count += 1
                
                progress_dialog.finish_operation(True, f"✅ 用当前配置批量保存完成: {success_count}/{total_count} 张")
                
            except Exception as e:
                progress_dialog.finish_operation(False, f"❌ 批量保存失败: {str(e)}")
        
        # 在后台线程执行
        threading.Thread(target=save_batch, daemon=True).start()
    
    def save_all_itmask_with_current_config(self):
        """用当前配置批量保存ITmask格式掩膜"""
        if not self.image_files:
            messagebox.showwarning("警告", "没有可处理的图片")
            return
        
        current_config = self.get_current_config()
        
        # 创建进度条弹窗
        progress_dialog = ProgressDialog(self.root, "用当前配置导出ITmask")
        
        def export_batch():
            try:
                itmask_dir = Path(__file__).parent / "ITmask"
                itmask_dir.mkdir(exist_ok=True)
                
                total_count = len(self.image_files)
                success_count = 0
                
                for i, image_path in enumerate(self.image_files):
                    # 检查是否取消
                    if progress_dialog.is_canceled():
                        progress_dialog.finish_operation(False, "用户取消了操作")
                        return
                    
                    # 更新进度
                    progress_dialog.update_progress(i+1, total_count, 
                                                   f"正在处理: {image_path.name} ({i+1}/{total_count})")
                    
                    # 临时加载图片
                    temp_image = safe_imread(image_path)
                    if temp_image is None:
                        continue
                    
                    # 读取标签
                    label_path = self.labels_folder / (image_path.stem + ".txt")
                    boxes = self.read_yolo_labels(str(label_path))
                    yolo_boxes = self.yolo_to_pixel_coords(boxes, 
                                                         temp_image.shape[1], 
                                                         temp_image.shape[0]) if boxes else []
                    
                    # 生成掩膜
                    mask, mask_refined, _ = self.ctd_model(temp_image, refine_mode=0, keep_undetected_mask=False)
                    
                    if yolo_boxes:
                        final_mask = self.filter_mask_with_yolo_boxes(mask_refined, yolo_boxes)
                    else:
                        final_mask = mask_refined
                    
                    # 使用当前配置调整大小
                    final_mask = self.adjust_mask_with_config(final_mask, current_config)
                    
                    # 创建ITmask格式
                    itmask = self.create_itmask(final_mask, temp_image.shape[1], temp_image.shape[0])
                    
                    # 保存
                    output_path = itmask_dir / (image_path.stem + ".png")
                    pil_image = Image.fromarray(itmask, 'RGBA')
                    pil_image.save(str(output_path), 'PNG')
                    success_count += 1
                
                progress_dialog.finish_operation(True, f"✅ 用当前配置 ITmask导出完成: {success_count}/{total_count} 张")
                
            except Exception as e:
                progress_dialog.finish_operation(False, f"❌ ITmask导出失败: {str(e)}")
        
        # 在后台线程执行
        threading.Thread(target=export_batch, daemon=True).start()
    
    def adjust_mask_with_config(self, mask, config):
        """用指定配置调整掩膜"""
        mask_size_factor = config.get('mask_size_factor', 1.0)
        extend_left = config.get('extend_left', 0)
        extend_right = config.get('extend_right', 0)
        extend_top = config.get('extend_top', 0)
        extend_bottom = config.get('extend_bottom', 0)
        
        adjusted_mask = mask
        
        # 应用整体大小调整
        if mask_size_factor != 1.0:
            if mask_size_factor > 1.0:
                kernel_size = int((mask_size_factor - 1.0) * 10) + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                adjusted_mask = cv2.dilate(adjusted_mask, kernel, iterations=1)
            else:
                kernel_size = int((1.0 - mask_size_factor) * 10) + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                adjusted_mask = cv2.erode(adjusted_mask, kernel, iterations=1)
        
        # 应用方向延伸 - 只支持正值
        if extend_left > 0 or extend_right > 0 or extend_top > 0 or extend_bottom > 0:
            adjusted_mask = self.apply_directional_extensions_with_config(adjusted_mask, config)
        
        return adjusted_mask
    
    def apply_directional_extensions_with_config(self, mask, config):
        """用指定配置应用单方向延伸 - 4个方向独立单向生长"""
        extend_left = config.get('extend_left', 0)
        extend_right = config.get('extend_right', 0)
        extend_top = config.get('extend_top', 0)
        extend_bottom = config.get('extend_bottom', 0)
        
        h, w = mask.shape
        result_mask = mask.copy()
        
        # 向上单向延伸
        if extend_top > 0:
            for i in range(1, int(extend_top) + 1):
                shifted = np.zeros_like(mask)
                if i < h:
                    shifted[:-i, :] = mask[i:, :]
                    result_mask = np.maximum(result_mask, shifted)
        
        # 向下单向延伸
        if extend_bottom > 0:
            for i in range(1, int(extend_bottom) + 1):
                shifted = np.zeros_like(mask)
                if i < h:
                    shifted[i:, :] = mask[:-i, :]
                    result_mask = np.maximum(result_mask, shifted)
        
        # 向左单向延伸
        if extend_left > 0:
            for i in range(1, int(extend_left) + 1):
                shifted = np.zeros_like(mask)
                if i < w:
                    shifted[:, :-i] = mask[:, i:]
                    result_mask = np.maximum(result_mask, shifted)
        
        # 向右单向延伸
        if extend_right > 0:
            for i in range(1, int(extend_right) + 1):
                shifted = np.zeros_like(mask)
                if i < w:
                    shifted[:, i:] = mask[:, :-i]
                    result_mask = np.maximum(result_mask, shifted)
        
        return result_mask
    
    def save_configs(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.image_configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def load_configs(self):
        """从文件加载配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.image_configs = json.load(f)
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.image_configs = {}
    
    def load_current_image(self):
        """加载当前图片"""
        if not self.image_files:
            return
        
        image_path = self.image_files[self.current_index]
        
        # 使用安全读取函数
        image_bgr = safe_imread(image_path)
        if image_bgr is None:
            self.progress_var.set(f"❌ 无法读取图片: {image_path.name}")
            return
        
        # 转换为RGB显示格式
        self.current_image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        
        # 更新信息
        self.image_info_label.config(text=f"{self.current_index + 1} / {len(self.image_files)}")
        self.progress_var.set(f"✅ 加载: {image_path.name}")
        
        # 尝试加载这张图片的配置
        current_image_name = image_path.stem
        if current_image_name in self.image_configs:
            self.apply_config(self.image_configs[current_image_name])
            self.progress_var.set(f"加载: {image_path.name} (已应用保存的配置)")
        
        # 加载YOLO框（用于显示指导，不自动生成掩膜）
        self.load_yolo_boxes_for_current_image()
        
        # 尝试从缓存加载掩膜，或重新生成已处理的掩膜
        cached_mask = self.get_cached_mask(current_image_name)
        if cached_mask is not None:
            self.current_mask = cached_mask
            self.progress_var.set(f"加载: {image_path.name} (已恢复掩膜缓存)")
        elif current_image_name in self.processed_images:
            # 已处理过但不在缓存中，重新生成
            self.progress_var.set(f"重新生成: {image_path.name}")
            self.generate_mask_for_current_image()
            self.progress_var.set(f"加载: {image_path.name} (已重新生成)")
        else:
            # 没有缓存也没处理过，清空当前掩膜
            self.current_mask = None
            self.progress_var.set(f"加载: {image_path.name} (请点击生成掩膜)")
        
        # 更新显示
        self.update_display()

    def cancel_batch_operation_func(self):
        """取消批量操作"""
        self.cancel_batch_operation = True
        self.progress_var.set("❌ 用户取消了操作")
        self.cancel_button.pack_forget()  # 隐藏取消按钮
    
    def show_cancel_button(self):
        """显示取消按钮"""
        self.cancel_batch_operation = False
        self.cancel_button.pack(side=tk.RIGHT)
    
    def hide_cancel_button(self):
        """隐藏取消按钮"""
        self.cancel_button.pack_forget()

    def create_itmask(self, mask, img_width, img_height):
        """创建ITmask格式：透明背景 + #D0FF14实心文字"""
        # 创建4通道RGBA图像（全透明）
        itmask = np.zeros((img_height, img_width, 4), dtype=np.uint8)
        
        # 将掩膜区域设置为#D0FF14颜色，不透明
        mask_area = mask > 127  # 二值化掩膜
        itmask[mask_area] = [20, 255, 208, 255]  # #D0FF14的BGR顺序 + Alpha
        
        return itmask
    
    def export_current_itmask(self):
        """导出当前页ITmask格式掩膜"""
        if self.current_mask is None:
            self.progress_var.set("警告: 没有可用的掩膜，请先生成掩膜预览")
            return
        
        try:
            # 获取调整后的掩膜
            final_mask = self.adjust_mask_size(self.current_mask, self.mask_size_factor)
            
            # 保存路径
            image_path = self.image_files[self.current_index]
            itmask_dir = Path(__file__).parent / "ITmask"
            itmask_dir.mkdir(exist_ok=True)
            output_path = itmask_dir / (image_path.stem + ".png")
            
            # 创建ITmask格式
            img_height, img_width = self.current_image.shape[:2]
            itmask = self.create_itmask(final_mask, img_width, img_height)
            
            # 使用PIL保存以支持RGBA
            pil_image = Image.fromarray(itmask, 'RGBA')
            pil_image.save(str(output_path), 'PNG')
            
            self.progress_var.set(f"✅ ITmask已导出: {image_path.stem}.png")
            
        except Exception as e:
            self.progress_var.set(f"❌ 导出ITmask失败: {str(e)}")
    
    def export_all_itmasks(self):
        """批量导出所有ITmask格式掩膜"""
        if not self.image_files:
            messagebox.showwarning("警告", "没有可处理的图片")
            return
        
        current_config = self.get_current_config()
        
        # 创建进度条弹窗
        progress_dialog = ProgressDialog(self.root, "批量导出ITmask")
        
        def export_batch():
            try:
                itmask_dir = Path(__file__).parent / "ITmask"
                itmask_dir.mkdir(exist_ok=True)
                
                total_count = len(self.image_files)
                success_count = 0
                
                for i, image_path in enumerate(self.image_files):
                    # 检查是否取消
                    if progress_dialog.is_canceled():
                        progress_dialog.finish_operation(False, "用户取消了操作")
                        return
                    
                    # 更新进度
                    progress_dialog.update_progress(i+1, total_count, 
                                                   f"正在处理: {image_path.name} ({i+1}/{total_count})")
                    
                    # 临时加载图片
                    temp_image = safe_imread(image_path)
                    if temp_image is None:
                        continue
                    
                    # 读取标签
                    label_path = self.labels_folder / (image_path.stem + ".txt")
                    boxes = self.read_yolo_labels(str(label_path))
                    yolo_boxes = self.yolo_to_pixel_coords(boxes, 
                                                         temp_image.shape[1], 
                                                         temp_image.shape[0]) if boxes else []
                    
                    # 生成掩膜
                    mask, mask_refined, _ = self.ctd_model(temp_image, refine_mode=0, keep_undetected_mask=False)
                    
                    if yolo_boxes:
                        final_mask = self.filter_mask_with_yolo_boxes(mask_refined, yolo_boxes)
                    else:
                        final_mask = mask_refined
                    
                    # 使用当前配置调整大小
                    final_mask = self.adjust_mask_with_config(final_mask, current_config)
                    
                    # 创建ITmask格式
                    itmask = self.create_itmask(final_mask, temp_image.shape[1], temp_image.shape[0])
                    
                    # 保存
                    output_path = itmask_dir / (image_path.stem + ".png")
                    pil_image = Image.fromarray(itmask, 'RGBA')
                    pil_image.save(str(output_path), 'PNG')
                    success_count += 1
                
                progress_dialog.finish_operation(True, f"✅ ITmask批量导出完成: {success_count}/{total_count} 张")
                
            except Exception as e:
                progress_dialog.finish_operation(False, f"❌ ITmask批量导出失败: {str(e)}")
        
        # 在后台线程执行
        threading.Thread(target=export_batch, daemon=True).start()

    def on_closing(self):
        """程序关闭时的清理工作"""
        # 清理掩膜缓存
        self.mask_cache.clear()
        self.current_mask = None
        print("已清理掩膜缓存")
        
        # 关闭程序
        self.root.destroy()

def main():
    root = tk.Tk()
    app = MaskGeneratorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()