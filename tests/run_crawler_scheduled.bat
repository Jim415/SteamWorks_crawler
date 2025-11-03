@echo off
REM SteamWorks Crawler - Scheduled Daily Execution Script
REM This script runs the crawler without requiring user interaction
REM Designed for Windows Task Scheduler

echo ============================================
echo SteamWorks Crawler - Scheduled Run
echo Date: %date% %time%
echo ============================================
echo.

REM Change to project directory
cd /d "D:\Steamworks_Crawler\SteamWorks_crawler"

REM Run the crawler (no virtual environment needed if using system Python)
echo Starting SteamWorks crawler...
python steamworks_crawler.py

REM Log completion
if %errorlevel% equ 0 (
    echo.
    echo [%date% %time%] Crawler completed successfully >> scheduled_runs.log
) else (
    echo.
    echo [%date% %time%] Crawler failed with error code %errorlevel% >> scheduled_runs.log
)

REM Don't pause - this is for automated runs
exit /b %errorlevel%

