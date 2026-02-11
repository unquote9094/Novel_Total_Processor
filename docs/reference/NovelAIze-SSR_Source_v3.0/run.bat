@echo off
setlocal
echo.
echo [NovelAIze-SSR v3.0 Source Runner]
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher.
    pause
    exit /b
)

:: Check if novel_aize_ssr directory exists
if not exist "novel_aize_ssr\main.py" (
    echo [Error] Source files not found correctly.
    echo Please ensure you are in the project root directory.
    pause
    exit /b
)

:: Run the application from project root
python novel_aize_ssr/main.py %*

if %errorlevel% neq 0 (
    echo.
    echo [Info] Application exited with error or closed.
    pause
)
endlocal
