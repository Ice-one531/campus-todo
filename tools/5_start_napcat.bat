@echo off
title NapCat 启动器
cd /d "%~dp0..\NapCat"
echo ============================================
echo   NapCat 启动器
echo ============================================
echo.
echo   这一步会：
echo     1. 关闭当前运行的 QQ
echo     2. 用 NapCat 注入方式重新启动 QQ
echo     3. 显示二维码，用手机 QQ 扫码登录
echo.
echo   注意：关闭 QQ 会中断当前聊天。
echo ============================================
echo.
pause

echo.
echo [1/2] 关闭 QQ...
if exist KillQQ.bat (call KillQQ.bat) else (taskkill /F /IM QQ.exe /T 2>nul)
timeout /t 3 /nobreak >nul

echo [2/2] 启动 NapCat 注入模式...
echo.
call launcher-user.bat

echo.
echo NapCat 已退出。
pause