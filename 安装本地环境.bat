@echo off
chcp 65001 >nul
setlocal EnableExtensions

title AI-image local environment installer

set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%env\python.exe"
set "BACKEND_REQ=%PROJECT_ROOT%backend\requirements.txt"
set "NPM_CMD=%PROJECT_ROOT%node-v24.15.0-win-x64\npm.cmd"

cd /d "%PROJECT_ROOT%"

echo [1/4] Checking local Python environment...
if not exist "%PYTHON_EXE%" (
    echo env\python.exe not found. Creating local env with Python launcher...
    py -3.12 -m venv env
    if errorlevel 1 (
        echo Failed to create env. Please install Python 3.12 first:
        echo https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
)

echo [2/4] Installing backend dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%PYTHON_EXE%" -m pip install -r "%BACKEND_REQ%"
if errorlevel 1 goto :failed

echo [3/4] Checking frontend runtime...
if exist "%NPM_CMD%" (
    set "NPM_BIN=%NPM_CMD%"
) else (
    set "NPM_BIN=npm"
)

echo [4/4] Installing frontend dependencies...
cd /d "%PROJECT_ROOT%frontend"
call "%NPM_BIN%" install
if errorlevel 1 goto :failed

echo.
echo Local environment is ready.
echo Backend Python: %PYTHON_EXE%
echo Start with the launcher bat file in the project root.
pause
exit /b 0

:failed
echo.
echo Installation failed. Check the error above.
pause
exit /b 1
