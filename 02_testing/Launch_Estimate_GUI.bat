@echo off
title NSO Crop Estimation Engine GUI
cd /d "%~dp002_Estimate_Calc_Py"

echo ========================================================
echo   Launching NSO Crop Yield & %%SE Estimation GUI
echo ========================================================

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
