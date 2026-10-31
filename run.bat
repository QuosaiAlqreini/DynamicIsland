@echo off
title Dynamic Island for Windows
cd /d "%~dp0"

echo ==========================================================
echo  Starting Dynamic Island for Windows
echo  (Antigravity & Claude Code Edition)
echo ==========================================================
echo.

python -m pip install -r requirements.txt --quiet
start pythonw app.py

echo Dynamic Island is running in the background!
echo Look at the top center of your screen or check the system tray icon.
timeout /t 3 >nul
exit
