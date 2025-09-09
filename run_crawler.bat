@echo off
REM SteamWorks Crawler - Daily Execution Script (Windows)
REM This script activates the virtual environment and runs the crawler

echo === SteamWorks Crawler - Daily Run ===
echo Date: %date% %time%
echo.

REM Change to script directory
cd /d "%~dp0"

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Run the crawler
echo Starting SteamWorks crawler...
python steamworks_crawler.py

REM Check exit status
if %errorlevel% equ 0 (
    echo.
    echo ✅ Crawler completed successfully!
    echo Check steamworks_crawler.log for details
) else (
    echo.
    echo ❌ Crawler failed!
    echo Check steamworks_crawler.log for error details
    pause
    exit /b 1
)

pause 