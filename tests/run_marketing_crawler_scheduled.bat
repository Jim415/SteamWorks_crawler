@echo off
REM SteamWorks Marketing Crawler - Scheduled Daily Execution Script
REM This script runs the marketing crawler without requiring user interaction
REM Designed for Windows Task Scheduler

echo ============================================
echo SteamWorks Marketing Crawler - Scheduled Run
echo Date: %date% %time%
echo ============================================
echo.

REM Change to project directory
cd /d "D:\Steamworks_Crawler\SteamWorks_crawler"

REM Run the marketing crawler (no virtual environment needed if using system Python)
echo Starting SteamWorks Marketing crawler...
python steamworks_marketing_crawler.py

REM Log completion
if %errorlevel% equ 0 (
    echo.
    echo [%date% %time%] Marketing Crawler completed successfully >> scheduled_runs.log
) else (
    echo.
    echo [%date% %time%] Marketing Crawler failed with error code %errorlevel% >> scheduled_runs.log
)

REM Don't pause - this is for automated runs
exit /b %errorlevel%


