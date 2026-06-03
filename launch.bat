@echo off
title Urea Simulation Launcher
cd /d "D:\Work\Urea Simulation\backend"

REM 1- start backend (keep window open for logs)
start "Urea Simulation Backend" cmd /k python main.py

REM wait for uvicorn to bind port 8000
timeout /t 3 /nobreak >nul

REM 2- open Chrome at the UI (fallback to default browser if Chrome missing)
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" (
  start "" "%CHROME%" "http://127.0.0.1:8000/"
) else (
  start "" "http://127.0.0.1:8000/"
)
exit
