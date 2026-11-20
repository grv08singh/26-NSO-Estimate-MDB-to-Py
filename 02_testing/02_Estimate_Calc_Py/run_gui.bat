@echo off
title NSO Crop Estimation Engine GUI
cd /d "%~dp0"

echo ========================================================
echo   Launching NSO Crop Yield & %%SE Estimation GUI
echo ========================================================

:: Check if miniconda python is available, otherwise use default python
if exist "C:\Users\Dex\miniconda3\python.exe" (
    "C:\Users\Dex\miniconda3\python.exe" "app_gui.py"
) else (
    python "app_gui.py"
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error.
    pause
)
