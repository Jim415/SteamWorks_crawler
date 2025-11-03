# Windows Task Scheduler Automation Setup

This guide explains how to configure Windows Task Scheduler to automatically refresh the dashboard and run alert checks daily.

## Overview

**Automation Flow:**
1. **3:30 PM** - SteamWorks crawler runs (existing task)
2. **3:45 PM** - Dashboard refresh executes (15-minute buffer)
3. **3:50 PM** - Alert checks run and send emails if needed

## Prerequisites

- Python installed and accessible from command line
- All dependencies installed (`requirements_visualization.txt`)
- Environment variables configured in `config/.env`
- Verified manual execution works

## Task 1: Dashboard Refresh

### Create the Task

1. Open **Task Scheduler** (search in Windows Start menu)

2. Click **Create Task** (not "Create Basic Task")

3. **General Tab:**
   - Name: `SteamWorks Dashboard Refresh`
   - Description: `Automated daily refresh of visualization dashboard`
   - Security options:
     - ☑ Run whether user is logged on or not
     - ☑ Run with highest privileges
   - Configure for: Windows 10/11

4. **Triggers Tab:**
   - Click **New**
   - Begin the task: `On a schedule`
   - Settings: `Daily`
   - Start: `3:45:00 PM`
   - Recur every: `1 days`
   - ☑ Enabled

5. **Actions Tab:**
   - Click **New**
   - Action: `Start a program`
   - Program/script: `python.exe` (or full path, e.g., `C:\Python311\python.exe`)
   - Add arguments: `refresh_dashboard.py`
   - Start in: `D:\Steamworks_Crawler\SteamWorks_crawler\Visualization`
   
   **Important**: Use absolute path for "Start in" directory

6. **Conditions Tab:**
   - ☐ Start the task only if the computer is on AC power (uncheck this)
   - ☑ Wake the computer to run this task (optional)

7. **Settings Tab:**
   - ☑ Allow task to be run on demand
   - ☑ Run task as soon as possible after a scheduled start is missed
   - ☐ Stop the task if it runs longer than: (uncheck, or set to 1 hour)
   - If the task is already running: `Do not start a new instance`

8. Click **OK** and enter your Windows password when prompted

### PowerShell Script Alternative

Create `run_dashboard_refresh.ps1`:

```powershell
# SteamWorks Dashboard Refresh Script
# Description: Executes dashboard refresh with logging

$ScriptDir = "D:\Steamworks_Crawler\SteamWorks_crawler\Visualization"
$LogFile = "$ScriptDir\scheduled_refresh.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Change to script directory
Set-Location $ScriptDir

# Log start
"[$Timestamp] Starting dashboard refresh..." | Out-File -FilePath $LogFile -Append

# Execute refresh script
try {
    python refresh_dashboard.py 2>&1 | Out-File -FilePath $LogFile -Append
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$Timestamp] Dashboard refresh completed successfully" | Out-File -FilePath $LogFile -Append
} catch {
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$Timestamp] ERROR: Dashboard refresh failed - $_" | Out-File -FilePath $LogFile -Append
}
```

Then in Task Scheduler:
- Program/script: `powershell.exe`
- Add arguments: `-ExecutionPolicy Bypass -File "D:\Steamworks_Crawler\SteamWorks_crawler\Visualization\run_dashboard_refresh.ps1"`

## Task 2: Alert Checks

### Create the Task

Follow the same process as Task 1, with these differences:

**General Tab:**
- Name: `SteamWorks Alert Checks`
- Description: `Daily KPI alert checks with email notifications`

**Triggers Tab:**
- Start: `3:50:00 PM` (5 minutes after dashboard refresh)

**Actions Tab:**
- Add arguments: `alerts.py`
- Start in: `D:\Steamworks_Crawler\SteamWorks_crawler\Visualization`

### PowerShell Script Alternative

Create `run_alerts.ps1`:

```powershell
# SteamWorks Alert Checks Script
# Description: Executes alert checks with logging

$ScriptDir = "D:\Steamworks_Crawler\SteamWorks_crawler\Visualization"
$LogFile = "$ScriptDir\scheduled_alerts.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Change to script directory
Set-Location $ScriptDir

# Log start
"[$Timestamp] Starting alert checks..." | Out-File -FilePath $LogFile -Append

# Execute alert script
try {
    python alerts.py 2>&1 | Out-File -FilePath $LogFile -Append
    $ExitCode = $LASTEXITCODE
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    if ($ExitCode -eq 0) {
        "[$Timestamp] Alert checks completed - no alerts triggered" | Out-File -FilePath $LogFile -Append
    } elseif ($ExitCode -eq 1) {
        "[$Timestamp] Alert checks completed - alerts triggered and sent" | Out-File -FilePath $LogFile -Append
    } else {
        "[$Timestamp] ERROR: Alert checks failed with exit code $ExitCode" | Out-File -FilePath $LogFile -Append
    }
} catch {
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$Timestamp] ERROR: Alert checks failed - $_" | Out-File -FilePath $LogFile -Append
}
```

## Testing the Tasks

### Test Dashboard Refresh

1. In Task Scheduler, right-click the task
2. Select **Run**
3. Check `refresh_dashboard.log` for output
4. Verify files created in `exports/` directory

### Test Alert Checks

1. In Task Scheduler, right-click the task
2. Select **Run**
3. Check `alerts.log` for output
4. Verify email received (if alerts triggered)

## Monitoring

### Task Execution History

1. Open Task Scheduler
2. Select the task
3. Click **History** tab
4. Review execution results, exit codes, and error messages

### Log Files

Monitor these files for issues:
- `refresh_dashboard.log` - Dashboard refresh output
- `alerts.log` - Alert system output
- `scheduled_refresh.log` - PowerShell script log (if using)
- `scheduled_alerts.log` - PowerShell script log (if using)

### Email Notifications

If alerts are configured correctly, you'll receive:
- Subject: `[SteamWorks Dashboard] Daily Alerts - YYYY-MM-DD`
- Recipient: `jimhanzhang@tencent.com`
- Content: Consolidated alert details

## Troubleshooting

### Task Doesn't Run

**Check:**
1. Task is enabled (right-click → Enable)
2. Trigger is configured correctly
3. User account has necessary permissions
4. Computer is awake at scheduled time

**Solution:**
- Review Task History for error codes
- Check Windows Event Viewer (Application log)
- Verify "Run whether user is logged on or not" is checked

### Task Runs but Fails

**Check:**
1. Python path is correct
2. Working directory is set correctly
3. Environment variables are accessible
4. User account has file system permissions

**Solution:**
- Test manually: `python refresh_dashboard.py`
- Check log files for Python errors
- Verify database connectivity from scheduled task context

### Python Not Found

**Check:**
1. Python is in system PATH
2. Full path to python.exe is specified

**Solution:**
Use absolute path in Task Scheduler:
- `C:\Python311\python.exe` (replace with your Python installation)
- Or: `C:\Users\[username]\AppData\Local\Programs\Python\Python311\python.exe`

### Environment Variables Not Loaded

**Check:**
1. `.env` file exists in `config/` directory
2. File has correct permissions
3. `python-dotenv` package is installed

**Solution:**
- Verify `.env` file path in scripts
- Use absolute paths in environment loading
- Consider system-level environment variables as alternative

### Database Connection Fails

**Check:**
1. MySQL service is running
2. Credentials in `.env` are correct
3. Network connectivity (if remote database)

**Solution:**
- Test connection: `python -m lib.db_connector`
- Verify MySQL service auto-starts on boot
- Check firewall rules

## Advanced Configuration

### Run on Multiple Schedules

To run dashboard refresh multiple times per day:

1. Edit the task
2. Go to **Triggers** tab
3. Add multiple triggers with different times

Example:
- Trigger 1: 3:45 PM (after main crawler)
- Trigger 2: 11:00 PM (end of day snapshot)

### Email on Task Failure

Configure email notifications for task failures:

1. Open Task Scheduler
2. Right-click task → **Properties**
3. **Actions** tab → **New**
4. Action: `Send an e-mail` (deprecated in newer Windows)

**Alternative**: Use PowerShell script with error handling that sends email on exceptions.

### Conditional Execution

Run task only if specific conditions met:

**Conditions Tab:**
- Only start if computer is idle for X minutes
- Wake computer to run (for laptop users)
- Run only on AC power (for battery life)

## Security Considerations

1. **Credentials Storage**: 
   - Store database credentials in `.env` file (gitignored)
   - Use Windows Credential Manager for SMTP passwords
   - Never hardcode credentials in scripts

2. **Task Permissions**:
   - Run with minimum required privileges
   - Use dedicated service account if available
   - Restrict file system permissions on logs

3. **Log Management**:
   - Regularly rotate log files
   - Monitor log file sizes
   - Archive old logs

## Maintenance

### Weekly Checks

- Verify tasks are running on schedule
- Review log files for errors
- Confirm emails are being received

### Monthly Review

- Check disk space in `exports/` directory
- Archive or delete old exported files
- Review alert thresholds and adjust if needed

## Backup

Backup these files for disaster recovery:

- All Python scripts and notebooks
- `config/.env` file (secure backup location)
- Task Scheduler XML exports (right-click task → Export)

Export task configuration:
```powershell
schtasks /query /tn "SteamWorks Dashboard Refresh" /xml > dashboard_task_backup.xml
schtasks /query /tn "SteamWorks Alert Checks" /xml > alerts_task_backup.xml
```

Restore task from XML:
```powershell
schtasks /create /tn "SteamWorks Dashboard Refresh" /xml dashboard_task_backup.xml
```

## Summary

With these tasks configured, your visualization system will:

✅ Automatically refresh daily at 3:45 PM
✅ Check for data quality issues at 3:50 PM  
✅ Send email alerts when problems detected
✅ Maintain execution logs for monitoring
✅ Export charts ready for presentations

All with zero manual intervention!

