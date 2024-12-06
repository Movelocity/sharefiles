@echo off
REM 切换到项目目录并激活 conda 环境
cd C:\projects\tools\file_service

call conda activate pdata
python main.py

pause