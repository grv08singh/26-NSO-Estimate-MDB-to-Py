@echo off
rem ---------------------------------------------------------------------------------------------------------------
rem  Start the Agri App on any Windows PC (10 / 11, 64-bit).
rem  It uses the first Python that can run the app:
rem    1. runtime\           the app's own Python (made once by setup_runtime.ps1; copy the whole folder to other PCs)
rem    2. .venv\             a virtual environment, if one was made here
rem    3. Anaconda / Miniconda in the usual places, if it has the app's libraries
rem  If none is there, it sets up runtime\ once (needs internet; no admin rights; nothing installed on the PC).
rem  set AGRI_DRYRUN=1 before running: only says which Python it would use.
rem ---------------------------------------------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
set "CHECK=import PySide6.QtWidgets, pandas, openpyxl, lxml, yaml, pyodbc, joblib"

rem 1. the app's own Python
if exist "runtime\READY.txt" if exist "runtime\python.exe" (
    set "PY=%~dp0runtime\python.exe"
    goto run
)

rem 2. a virtual environment
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "%CHECK%" >nul 2>&1 && (
        set "PY=%~dp0.venv\Scripts\python.exe"
        goto run
    )
)

rem 3. Anaconda / Miniconda
for %%P in ("%USERPROFILE%\anaconda3\python.exe" "%USERPROFILE%\miniconda3\python.exe" "%LOCALAPPDATA%\anaconda3\python.exe" "%LOCALAPPDATA%\miniconda3\python.exe" "%ProgramData%\anaconda3\python.exe" "%ProgramData%\miniconda3\python.exe") do (
    if exist %%P (
        %%P -c "%CHECK%" >nul 2>&1 && (
            set "PY=%%~P"
            goto run
        )
    )
)

rem 4. nothing ready: set up the app's own Python once
if defined AGRI_DRYRUN (
    echo No ready Python found - would set up runtime\ now.
    exit /b 0
)
echo.
echo  First start on this PC: setting up the app's own Python in "%~dp0runtime"
echo  (one time only, needs internet, a few minutes; nothing is installed on the PC itself).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_runtime.ps1" -Root "%~dp0."
if errorlevel 1 (
    echo.
    echo  The set-up did not finish - see 03_logs\setup_runtime.log
    pause
    exit /b 1
)
set "PY=%~dp0runtime\python.exe"

:run
if defined AGRI_DRYRUN (
    echo Would start the app with: %PY%
    exit /b 0
)
"%PY%" app.py
if errorlevel 1 pause
endlocal
