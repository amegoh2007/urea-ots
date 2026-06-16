@echo off
title Urea Simulation Launcher
cd /d "D:\Work\Urea Simulation\backend"

REM 1- start backend (keep window open for logs)
start "Urea Simulation Backend" cmd /k python main.py

REM 2- wait until uvicorn actually answers on port 8000 (poll, do NOT blind-wait).
REM    Fixed sleeps race the Python cold-start and open Chrome on a dead port -> blank page.
echo Waiting for backend on http://127.0.0.1:8000 ...
set /a _tries=0
:wait
curl.exe -s -o nul http://127.0.0.1:8000/
if not errorlevel 1 goto ready
set /a _tries+=1
if %_tries% geq 60 goto giveup
timeout /t 1 /nobreak >nul
goto wait
:giveup
echo WARNING: backend did not respond after 60s; opening browser anyway.
:ready

REM 3- open Chrome at the UI (fallback to default browser if Chrome missing)
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" (
  start "" "%CHROME%" "http://127.0.0.1:8000/"
) else (
  start "" "http://127.0.0.1:8000/"
)
exit
