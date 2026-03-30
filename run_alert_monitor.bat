@echo off
REM SteamWorks Crawler Alert Monitor - Scheduled Execution Script
REM This script runs the alert monitor without requiring user interaction
REM Designed for Windows Task Scheduler

echo ============================================
echo SteamWorks Crawler Alert Monitor
echo Date: %date% %time%
echo ============================================
echo.

REM Change to project directory
cd /d "D:\Steamworks_Crawler\SteamWorks_crawler"

REM Use full path to python.exe
set PYTHON_PATH=C:\Users\jimhanzhang\AppData\Local\Programs\Python\Python314\python.exe

REM Verify Python exists
if not exist "%PYTHON_PATH%" (
    echo ERROR: Python not found at: %PYTHON_PATH%
    echo Trying python from PATH...
    python crawler_alert_monitor.py
    if %errorlevel% neq 0 (
        echo ERROR: Python not found or script failed
        echo Error code: %errorlevel%
        exit /b %errorlevel%
    )
) else (
    echo Using Python: %PYTHON_PATH%
    "%PYTHON_PATH%" crawler_alert_monitor.py
    if %errorlevel% neq 0 (
        echo ERROR: Script failed with error code: %errorlevel%
        exit /b %errorlevel%
    )
)

REM Log completion
echo.
echo [%date% %time%] Alert monitor completed >> alert_monitor_scheduled.log
exit /b 0

