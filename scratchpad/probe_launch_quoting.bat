@echo off
REM ============================================================================================
REM Evidence for the launch.bat quoting of:
REM
REM     start "Urea Simulation Backend" cmd /k ""%PY%" main.py"
REM
REM `start` + `cmd /k` + a quoted title + a quoted exe + a quoted argument is the classic place
REM Windows batch silently does the wrong thing (start eats the first quoted token as the window
REM title, cmd strips outer quotes).  This proves the doubled-quote form survives -- and it runs
REM the script from a path CONTAINING A SPACE, which is the case that actually breaks naive forms.
REM
REM Uses /c and a 1-line stand-in for main.py so nothing is left running.
REM
REM Run:  cmd /c scratchpad\probe_launch_quoting.bat
REM Expect: QUOTING-OK plus the resolved interpreter path, exit 0.
REM ============================================================================================
setlocal
set "SP=%~dp0"
set "PY=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY%" (echo SKIPPED - pinned interpreter not present & exit /b 0)

REM stand-in "main.py", deliberately given a name with a space in it
> "%SP%_fake main.py" echo import pathlib, sys; pathlib.Path(sys.argv[1]).write_text("LAUNCHED by " + sys.executable)
if exist "%SP%_marker.txt" del "%SP%_marker.txt"

REM --- exactly launch.bat's form, but /c instead of /k ---
start "Urea Simulation Backend" /wait cmd /c ""%PY%" "%SP%_fake main.py" "%SP%_marker.txt""

if not exist "%SP%_marker.txt" (
  echo QUOTING-FAILED - marker not written
  del "%SP%_fake main.py" 2>nul
  exit /b 1
)
echo QUOTING-OK
type "%SP%_marker.txt"
echo.
del "%SP%_fake main.py" "%SP%_marker.txt" 2>nul
exit /b 0
