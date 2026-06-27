@echo off
title AI Jobs - Setup
echo Starting setup...
python setup.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Setup script failed. Make sure Python is installed and added to your system PATH.
)
pause
