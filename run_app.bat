@echo off
title InfiniteLaygu Extractor - Universal Game Asset & Cutscene Suite
cd /d "%~dp0"

echo ========================================================
echo   InfiniteLaygu Extractor - Universal Game Asset Suite
echo ========================================================
echo.
echo Starting 4K Ultra-Sharp GUI Application...
python app.py
if errorlevel 1 (
    echo.
    echo [ERROR] Application stopped with an error code.
    pause
)
