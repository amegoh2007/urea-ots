@echo off
REM ============================================================================================
REM Evidence for the launch.bat interpreter-resolution fix (slot 11, 2026-07-23).
REM Contains the :try guard COPIED VERBATIM from launch.bat, exercised on three cases:
REM
REM   1. a file that exists, RUNS, and EXITS 0 but is not Python  -> must be REJECTED
REM   2. the real interpreter, reached only by falling past (1)   -> must be TAKEN
REM   3. nothing resolvable at all                                -> must reach :nopython
REM
REM Case (1) is the one that matters.  The first version of this guard checked only the exit code,
REM and a copy of cmd.exe named python.exe ignores the arguments and exits 0 -- so an
REM exit-code-only guard ACCEPTS it.  That is not hypothetical for this repo: the whole point of
REM the fix is that %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe may be a stub rather than an
REM interpreter.  Hence the guard demands the process PRINT a token: only something that actually
REM evaluated the expression can.  `range(310,600)` instead of `>=` because `<` and `>` are
REM redirection operators inside a .bat.
REM
REM Run:  cmd /c scratchpad\probe_launch_resolve.bat
REM Expect: REJECT-OK, FALLTHROUGH-OK, NOPYTHON-OK, then ALL-OK / exit 0.
REM ============================================================================================
setlocal
set "SP=%~dp0"
set "FAKE=%SP%_fakestub"
if not exist "%FAKE%" mkdir "%FAKE%"
copy /y "%SystemRoot%\System32\cmd.exe" "%FAKE%\python.exe" >nul

echo === case 1: a non-Python that exits 0 ===
"%FAKE%\python.exe" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo   SKIPPED - stand-in did not exit 0, so it does not test what this is for
) else (
  echo   stand-in exits 0, so an exit-code-only guard would take it
)
"%FAKE%\python.exe" -c "import sys;print('PY_OK' if sys.version_info[0]*100+sys.version_info[1] in range(310,600) else 'PY_OLD')" 2>nul | find "PY_OK" >nul
if errorlevel 1 (echo   REJECT-OK) else (echo   REJECT-FAILED & goto fail)

echo === case 2: falls through to the real interpreter ===
set "PY="
call :try "%FAKE%\python.exe"
call :try "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Python\pythoncore-*") do call :try "%%d\python.exe"
if not defined PY for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do call :try "%%i"
if not defined PY for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do call :try "%%i"
if not defined PY (echo   FALLTHROUGH-FAILED - resolved nothing & goto fail)
echo %PY% | find /i "_fakestub" >nul
if not errorlevel 1 (echo   FALLTHROUGH-FAILED - took the stub & goto fail)
echo   using %PY%
"%PY%" -c "import sys; print('  version', '.'.join(map(str, sys.version_info[:3])))"
echo   FALLTHROUGH-OK

echo === case 3: nothing resolvable ===
set "PY="
call :try "%SP%\does-not-exist\python.exe"
if defined PY (echo   NOPYTHON-FAILED & goto fail)
echo   NOPYTHON-OK

rmdir /s /q "%FAKE%" 2>nul
echo.
echo ALL-OK
exit /b 0

:fail
rmdir /s /q "%FAKE%" 2>nul
exit /b 1

REM --- verbatim from launch.bat -----------------------------------------------------------------
:try
if defined PY exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys;print('PY_OK' if sys.version_info[0]*100+sys.version_info[1] in range(310,600) else 'PY_OLD')" 2>nul | find "PY_OK" >nul
if errorlevel 1 exit /b 0
set "PY=%~1"
exit /b 0
