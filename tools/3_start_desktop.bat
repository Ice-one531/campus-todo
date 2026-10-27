@echo off
title 校园待办
cd /d "E:\CampusTodo\app"
echo 正在启动桌面端（会自动拉起后台服务）...
"C:\Users\20289_53h193v\.venv_campus\Scripts\python.exe" desktop_app.py
if errorlevel 1 pause