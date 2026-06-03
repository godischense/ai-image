@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
echo ==========================================
echo          AI-image 图片生成应用
echo ==========================================
echo.

cd /d "%~dp0"

for /f "tokens=1* delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    set "ip=%%b"
    set "ip=!ip: =!"
    goto :found
)
:found

echo [INFO] 正在启动后端服务...
echo [INFO] 局域网访问地址: http://!ip!:5678
echo.

start "AI-image后端" "env\python.exe" "backend\app.py"

echo [INFO] 等待后端服务启动...
timeout /t 3 /nobreak >nul

echo [INFO] 正在自动打开浏览器...
start "" "http://!ip!:5678"

echo.
echo [INFO] 浏览器已打开，请勿关闭此窗口以保持后端运行。
pause
