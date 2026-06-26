@echo off
chcp 65001 >nul
setlocal EnableExtensions

title AI-image launcher

set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%env\python.exe"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "WWW_INDEX=%PROJECT_ROOT%www\index.html"
set "PORT=5678"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONLEGACYWINDOWSSTDIO=utf-8"
set "PATH=%PROJECT_ROOT%env;%PROJECT_ROOT%env\Scripts;%PROJECT_ROOT%env\Library\bin;%PATH%"

cd /d "%PROJECT_ROOT%"

if not exist "%PYTHON_EXE%" (
    echo Local embedded Python not found: %PYTHON_EXE%
    echo Please make sure env\python.exe exists in the project root.
    pause
    exit /b 1
)

if not exist "%WWW_INDEX%" (
    echo Frontend build output not found: %WWW_INDEX%
    echo Please build the frontend first so www\index.html exists.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%P in (`"%PYTHON_EXE%" "%BACKEND_DIR%\services\get_server_port.py" 2^>nul`) do (
    set "PORT=%%P"
    goto :port_loaded
)

:port_loaded
echo %PORT%| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 set "PORT=5678"

echo Python: %PYTHON_EXE%
set "LOCAL_URL=http://localhost:%PORT%"

echo URL: %LOCAL_URL%
echo Backend is starting. Keep this window open.

start "" /min cmd /c "timeout /t 3 /nobreak >nul & rundll32 url.dll,FileProtocolHandler %LOCAL_URL%"

cd /d "%BACKEND_DIR%"
"%PYTHON_EXE%" app.py

echo.
echo Backend service has exited.
pause
