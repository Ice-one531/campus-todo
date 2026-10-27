@echo off
title 校园待办 - 消息服务
cd /d "E:\CampusTodo\app"
echo ============================================
echo   校园通知智能待办 - 消息服务
echo ============================================
echo.
echo   控制台: http://127.0.0.1:8000/console/
echo   健康检查: http://127.0.0.1:8000/health
echo.
echo   关闭这个窗口 = 停止服务
echo ============================================
echo.
"C:\Users\20289_53h193v\.venv_campus\Scripts\python.exe" main.py
pause