@echo off
title Web Crawler + Gemini AI [DEBUG MODE]
cd /d "%~dp0"
echo ==========================================
echo   DEBUG MODE - Log se duoc luu vao file
echo   debug_log.txt
echo ==========================================
echo.
echo Dang khoi dong app...
uv run main.py > debug_log.txt 2>&1
echo.
echo ==========================================
echo   App da dong. Noi dung debug log:
echo ==========================================
type debug_log.txt
echo.
echo ==========================================
echo Log da duoc luu tai: %~dp0debug_log.txt
echo Hay copy noi dung file nay va gui cho Claude.
pause
