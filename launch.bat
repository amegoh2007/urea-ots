@echo off
title Urea Simulation Launcher
cd /d "D:\Work\Urea Simulation\backend"

REM 1- resolve a REAL interpreter before doing anything with it.
REM    Bare `python` on PATH is an App Execution Alias at
REM    %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe.  Measured 2026-07-23 it forwards to
REM    pythoncore-3.14-64 and works fine -- but that forwarding is a per-user Windows Settings
REM    toggle ("App execution aliases") living outside this repo.  Turn it off, uninstall
REM    PyManager, or let a Store entry win the PATH race, and the SAME command silently becomes
REM    the Microsoft Store stub: it prints "Python was not found" and exits non-zero.  That has
REM    happened on this machine before -- it is why CLAUDE.md 7 exists.  So resolve explicitly
REM    and PROVE the interpreter runs, rather than trusting PATH order.
REM    Each candidate goes through :try, which EXECUTES it -- a path that exists is not an
REM    interpreter that runs, the stub exists too -- and rejects anything under 3.10.  A rejected
REM    candidate falls through to the next one, so a stale pythoncore-* directory left behind by a
REM    version upgrade cannot dead-end the launcher.
set "PY="
call :try "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Python\pythoncore-*") do call :try "%%d\python.exe"
if not defined PY for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do call :try "%%i"
if not defined PY for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do call :try "%%i"
if not defined PY goto nopython
echo Using Python: %PY%

REM 2- install / update Python dependencies (silent on second run when already up-to-date)
echo Checking Python dependencies...
"%PY%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: pip install failed against %PY%.
    pause
    exit /b 1
)

REM 3- start backend (keep window open for logs)
start "Urea Simulation Backend" cmd /k ""%PY%" main.py"

REM 4- wait until uvicorn actually answers on port 8000 (poll, do NOT blind-wait).
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

REM 5- open Chrome at the UI (fallback to default browser if Chrome missing)
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" (
  start "" "%CHROME%" "http://127.0.0.1:8000/"
) else (
  start "" "http://127.0.0.1:8000/"
)
exit

:nopython
echo.
echo ERROR: no working Python 3.10+ interpreter found.
echo.
echo   Tried, in order:
echo     1. %%LOCALAPPDATA%%\Python\pythoncore-3.14-64\python.exe   ^(the pinned install^)
echo     2. py -3                                                  ^(the PEP 397 launcher^)
echo     3. python                                                 ^(PATH / App Execution Alias^)
echo.
echo   If `python -V` in a terminal prints "Python was not found" or opens the
echo   Microsoft Store, the App Execution Alias is pointing at the Store stub.
echo   Fix it in: Settings ^> Apps ^> Advanced app settings ^> App execution aliases
echo   ^(turn OFF python.exe / python3.exe^), or reinstall Python from python.org.
echo.
pause
exit /b 1

REM --- accept %1 as the interpreter only if it EXISTS, RUNS, and IDENTIFIES as Python 3.10+ ----
REM     Unreachable by fall-through: every path above ends in `exit` or `exit /b`.
REM     The exit code alone is NOT enough -- tested, a copy of cmd.exe named python.exe ignores the
REM     arguments and exits 0, so an exit-code-only guard accepts it.  Demand that the process
REM     PRINT the token instead: only a real interpreter that actually evaluated the expression can.
REM     `range(310,600)` rather than `>=` on purpose -- `<` and `>` are redirection operators here.
:try
if defined PY exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys;print('PY_OK' if sys.version_info[0]*100+sys.version_info[1] in range(310,600) else 'PY_OLD')" 2>nul | find "PY_OK" >nul
if errorlevel 1 exit /b 0
set "PY=%~1"
exit /b 0
