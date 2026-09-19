@echo off
title WorkWise AI Launcher
echo ==========================================================================
echo   WorkWise AI — AI Workforce Decision and Resource Allocation Launcher
echo ==========================================================================

if not exist .venv (
    echo Creating Python virtual environment...
    py -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
)

echo Launching WorkWise AI Web Server...
.\.venv\Scripts\python.exe run.py
pause
