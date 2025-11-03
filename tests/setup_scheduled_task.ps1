# SteamWorks Crawler - Windows Task Scheduler Setup Script
# This PowerShell script automatically creates a scheduled task to run the crawler daily at 3:30pm

# Configuration
$TaskName = "SteamWorks_Crawler_Daily"
$TaskDescription = "Runs the SteamWorks crawler daily at 3:30pm to collect Steam analytics data"
$ScriptPath = "D:\Steamworks_Crawler\SteamWorks_crawler\tests\run_crawler_scheduled.bat"
$WorkingDirectory = "D:\Steamworks_Crawler\SteamWorks_crawler"
$RunTime = "15:30"  # 3:30 PM in 24-hour format

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "SteamWorks Crawler - Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "  1. Right-click PowerShell" -ForegroundColor Yellow
    Write-Host "  2. Select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "  3. Run this script again" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Checking if task already exists..." -ForegroundColor Yellow

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Task '$TaskName' already exists!" -ForegroundColor Yellow
    $response = Read-Host "Do you want to delete and recreate it? (Y/N)"
    
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host "Deleting existing task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Existing task deleted." -ForegroundColor Green
    } else {
        Write-Host "Setup cancelled." -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 0
    }
}

Write-Host "Creating scheduled task..." -ForegroundColor Yellow

# Create the action (what to run)
$action = New-ScheduledTaskAction -Execute $ScriptPath -WorkingDirectory $WorkingDirectory

# Create the trigger (when to run - daily at 3:30 PM)
$trigger = New-ScheduledTaskTrigger -Daily -At $RunTime

# Create task settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Get current user
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

# Create the principal (run with highest privileges)
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest

# Register the task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null
    
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "SUCCESS! Task created successfully!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:" -ForegroundColor Cyan
    Write-Host "  - Task Name: $TaskName" -ForegroundColor White
    Write-Host "  - Schedule: Daily at $RunTime (3:30 PM)" -ForegroundColor White
    Write-Host "  - Script: $ScriptPath" -ForegroundColor White
    Write-Host "  - User: $currentUser" -ForegroundColor White
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "  1. The task will run automatically every day at 3:30 PM" -ForegroundColor White
    Write-Host "  2. Check logs in: $WorkingDirectory\steamworks_crawler.log" -ForegroundColor White
    Write-Host "  3. To test now, run: run_crawler_scheduled.bat" -ForegroundColor White
    Write-Host "  4. To view task: Open Task Scheduler -> Task Scheduler Library" -ForegroundColor White
    Write-Host ""
    Write-Host "To manually run the task now, type: Y" -ForegroundColor Yellow
    $runNow = Read-Host "Run task now for testing? (Y/N)"
    
    if ($runNow -eq 'Y' -or $runNow -eq 'y') {
        Write-Host ""
        Write-Host "Starting task..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Task started! Check the log file for progress." -ForegroundColor Green
    }
    
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to create task!" -ForegroundColor Red
    Write-Host "Error details: $_" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Read-Host "Press Enter to exit"

