@echo off
title Install Playwright Browsers
cd /d "%~dp0"
echo ============================================
echo  Installing Playwright Chromium browser...
echo ============================================
echo.
uv run python -m playwright install chromium
echo.
echo ============================================
echo  Done! You can now run the app.
echo ============================================
pause
