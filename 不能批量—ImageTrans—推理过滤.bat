@echo off
REM ���� Conda ����
call conda activate yolov11

REM ���� Python �ű���֧���Ϸ��ļ�·������
python tuiliguoluvMASKImageTrans.py %*

REM ȡ������ Conda ����
call conda deactivate

REM ��ͣ�Ա�鿴���
echo �����������...
pause >nul
