import sys
import os
import shutil
from rfdetr import RFDETRBase
print("脚本开始")
if len(sys.argv) < 2:
    print("请拖拽模型文件到此脚本执行")
    sys.exit(1)
checkpoint_path = sys.argv[1]
print("模型文件路径:", checkpoint_path)
if not os.path.exists(checkpoint_path):
    print("模型文件不存在！")
    sys.exit(1)

# 脚本目录
script_dir = os.path.dirname(os.path.abspath(__file__))
# 准备输出文件名
onnx_filename = os.path.splitext(os.path.basename(checkpoint_path))[0] + ".onnx"
onnx_path = os.path.join(script_dir, onnx_filename)

# 检查并删除可能存在的output目录
output_dir = os.path.join(script_dir, "output")
if os.path.exists(output_dir):
    print(f"删除已存在的output目录: {output_dir}")
    shutil.rmtree(output_dir)

# 加载模型
model = RFDETRBase(pretrain_weights=checkpoint_path)
print("模型加载完成")
print(f"ONNX文件将导出到: {onnx_path}")

# 尝试导出
try:
    # 尝试直接检查RFDETRBase的源代码
    # 先获取类的源代码路径
    import inspect
    rfdetr_file = inspect.getfile(RFDETRBase)
    print(f"RFDETRBase类定义在: {rfdetr_file}")
    
    # 执行导出
    model.export(onnx_path=onnx_path)
    
    # 处理输出
    default_output_path = os.path.join(script_dir, "output", "inference_model.onnx")
    if os.path.exists(default_output_path):
        # 如果在output目录生成了文件，复制到正确位置并删除output目录
        shutil.copy(default_output_path, onnx_path)
        print(f"ONNX模型已从默认位置复制到: {onnx_path}")
        
        # 删除output目录
        print(f"删除临时output目录")
        shutil.rmtree(output_dir)
    
    print("ONNX 导出完成")
    
    # 验证最终文件存在
    if os.path.exists(onnx_path):
        print(f"成功: ONNX文件已保存到 {onnx_path}")
    else:
        print(f"错误: 未能在预期位置找到ONNX文件")
        
except Exception as e:
    print(f"导出过程中出现错误: {e}")
    import traceback
    traceback.print_exc()