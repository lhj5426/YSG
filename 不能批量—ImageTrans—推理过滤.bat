@echo off
REM 激活 Conda 环境
call conda activate yolov11

REM 运行 Python 脚本，支持拖放文件路径传递
python tuiliguoluvMASKImageTrans.py %*

REM 取消激活 Conda 环境
call conda deactivate

REM 暂停以便查看结果
echo 按任意键继续...
pause >nul
