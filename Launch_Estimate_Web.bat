@echo off
title NSO Crop Estimation Engine Web App
cd /d "%~dp002_Estimate_Calc_Py"

echo ========================================================
echo   Launching NSO Crop Yield & %%SE Web Dashboard
echo ========================================================

if exist "C:\Users\Dex\miniconda3\Scripts\streamlit.exe" (
    "C:\Users\Dex\miniconda3\Scripts\streamlit.exe" run "app_web.py"
) else (
    streamlit run "app_web.py"
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error.
    pause
)
