@echo off
REM ���� Conda ����
call conda activate RFDETR

REM ���� Python �ű���֧���Ϸ��ļ�·������
python YOLOzhuanCOCO.py %*

REM ȡ������ Conda ����
call conda deactivate

REM ��ͣ�Ա�鿴���
echo �����������...
pause >nul
