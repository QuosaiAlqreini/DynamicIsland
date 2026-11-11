@echo off
title Dynamic Island for Windows
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install it with:
    echo     winget install -e --id Python.Python.3.12
    echo then open a new terminal and run this file again.
    pause
    exit /b 1
)

echo Updating to the latest version (skipped if this is not a git copy)...
git pull --ff-only 2>nul

echo Checking dependencies...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo Could not install dependencies. See the message above.
    pause
    exit /b 1
)

start "" pythonw app.py
echo Dynamic Island is running. Look at the top of your screen or the tray icon.
timeout /t 2 >nul
exit /b 0
