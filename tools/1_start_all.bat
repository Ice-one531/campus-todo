@echo off
title 校园待办 - 一键启动
echo ============================================
echo   一键启动：服务 + 打开控制台
echo ============================================
start "校园待办服务" /min cmd /c ""C:\Users\20289_53h193v\.venv_campus\Scripts\python.exe" "E:\CampusTodo\app\main.py""
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:8000/console/"
echo.
echo 已启动。控制台应该在浏览器里打开了。
echo 关闭那个最小化的"校园待办服务"窗口即可停止服务。
timeout /t 3 /nobreak >nul