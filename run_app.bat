@echo off
title Ananta Asset Extractor and Dataminer
cd /d "%~dp0"

echo ========================================================
echo   Ananta Asset Extractor and Dataminer (Client 4229938)
echo ========================================================
echo.
echo Starting 4K Ultra-Sharp GUI Application...
python app.py
if errorlevel 1 (
    echo.
    echo [ERROR] Application stopped with an error code.
    pause
)
