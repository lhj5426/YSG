@echo off
cd /d %~dp0
call conda activate RFDETR
python RfderzhuanONNX.py %1
