@echo off
REM ���� Conda ����
call conda activate cdetector

REM ���� Python �ű���֧���Ϸ��ļ�·������
python tuozhuai.py %*

REM ȡ������ Conda ����
call conda deactivate

REM ��ͣ�Ա�鿴���
echo �����������...
pause >nul
