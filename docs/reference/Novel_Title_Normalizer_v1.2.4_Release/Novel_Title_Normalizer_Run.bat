@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ==================================================
echo   Novel Title Normalizer (Launcher)
echo ==================================================
echo.

:: Check if pwsh (PowerShell Core) is available
where pwsh >nul 2>nul
if %errorlevel% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "scripts\Novel_Title_Normalizer_v1.2.4.ps1"
) else (
    echo [ERROR] PowerShell 7 ^(pwsh^) is not found. Falling back to Windows PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\Novel_Title_Normalizer_v1.2.4.ps1"
)

echo.
echo ==================================================
echo   Program finished.
echo ==================================================
pause
