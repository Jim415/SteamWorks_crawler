# SteamWorks Crawler Alert Monitor - Usage Guide

## Overview

The alert monitor checks if the crawler ran successfully by:
1. ✅ Validating database rows (checking for all 4 games with correct `stat_date`)
2. ✅ Analyzing log files for errors
3. ✅ Sending WeCom alerts for both success and failure cases

## Quick Start

### Step 1: Set Up WeCom Webhook

Follow the instructions in `WECOM_WEBHOOK_SETUP.md` to get your webhook URL.

**Quick Summary:**
1. Open WeCom app (企业微信)
2. Create or open a group chat
3. Add a "Group Robot" (群机器人)
4. Copy the webhook URL

### Step 2: Configure the Alert Monitor

Run the alert monitor script for the first time:

```powershell
python crawler_alert_monitor.py
```

The script will prompt you to enter your WeCom webhook URL. Enter it when prompted, and it will be saved to `alert_config.json`.

**Alternatively**, you can manually create `alert_config.json`:

```json
{
  "wecom_webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"
}
```

### Step 3: Test the Alert Monitor

Run the script manually to test:

```powershell
python crawler_alert_monitor.py
```

You should receive an alert in your WeCom group (either success or failure depending on current database state).

### Step 4: Schedule the Alert Monitor

Set up Windows Task Scheduler to run the monitor daily at **4:35 PM Beijing Time** (5 minutes after crawler starts).

**Option A: Using PowerShell Script (Recommended)**

Create a task scheduler script `tests/setup_alert_monitor_task.ps1` or use Task Scheduler UI:

1. Open **Task Scheduler**
2. Click **Create Task**
3. **General Tab:**
   - Name: `SteamWorks_Crawler_Alert_Monitor`
   - Description: `Daily alert monitor for crawler status`
   - Run whether user is logged on or not: ✅
   - Run with highest privileges: ✅

4. **Triggers Tab:**
   - New trigger: Daily
   - Start: `16:35:00` (4:35 PM)
   - Recur every: `1 days`

5. **Actions Tab:**
   - Action: `Start a program`
   - Program/script: `python.exe` (or full path)
   - Add arguments: `crawler_alert_monitor.py`
   - Start in: `D:\Steamworks_Crawler\SteamWorks_crawler`

6. **Conditions Tab:**
   - Uncheck "Start the task only if the computer is on AC power"

7. **Settings Tab:**
   - Allow task to be run on demand: ✅
   - Run task as soon as possible after a scheduled start is missed: ✅

## How It Works

### Execution Flow

1. **4:30 PM Beijing**: Crawler runs (your existing scheduled task)
2. **4:35 PM Beijing**: Alert monitor runs (new scheduled task)
3. Monitor checks:
   - Database for all 4 games with correct `stat_date`
   - Log file for errors in last 10 minutes
4. Sends alert:
   - ✅ **Success alert** if all checks pass
   - 🚨 **Failure alert** if issues detected

### Alert Messages

**Success Alert:**
```
✅ SteamWorks Crawler Alert - Success

**Date**: 2025-12-01 16:35:00 (Beijing Time)

**Status**: All crawler runs completed successfully

All 4 games have data in database with correct stat_date.
```

**Failure Alert:**
```
🚨 SteamWorks Crawler Alert - Failure

**Date**: 2025-12-01 16:35:00 (Beijing Time)
**Expected stat_date**: 2025-11-30 (PST)

**Game Status**:
✓ Delta Force (2507950) - OK
✓ Arena Breakout: Infinite (2073620) - OK
✗ Road to Empress (3478050) - MISSING
✓ Terminull Brigade (3104410) - OK

**Issue Summary**:
- Missing data for 1 game(s): Road to Empress

**Log Errors**:
- [2025-12-01 16:32] ERROR - Manual login required for Regions Revenue Page
```

## Configuration

### Expected Games

The monitor checks for these 4 games (hardcoded in script):
- Delta Force (2507950)
- Arena Breakout: Infinite (2073620)
- Road to Empress (3478050)
- Terminull Brigade (3104410)

**To update games list**: Edit `EXPECTED_GAMES` in `crawler_alert_monitor.py` (lines 35-40)

### Database Configuration

Uses the shared `db_config.py` module, which reads database settings from environment variables or the project `.env` file:

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

If the database moves again, update `.env`; `crawler_alert_monitor.py` and the crawler will use the same connection settings.

## Log Files

- **Monitor log**: `crawler_alert_monitor.log` (logs all monitor executions)
- **Crawler log**: `steamworks_crawler.log` (checked for errors)

## Troubleshooting

### "Webhook URL not configured"
- Run the script manually and enter webhook URL when prompted
- Or create `alert_config.json` manually

### "Alert not sent (no webhook URL configured)"
- Check that `alert_config.json` exists and contains valid webhook URL
- Verify webhook URL format: `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...`

### "Failed to send WeCom alert"
- Verify webhook URL is correct
- Test webhook URL using PowerShell (see `WECOM_WEBHOOK_SETUP.md`)
- Check network connectivity

### Database connection errors
- Verify the configured MySQL/TencentDB instance is reachable
- Check database credentials in `.env` match your setup
- Ensure database `steamworks_crawler` exists

## Manual Testing

Test the monitor without waiting for scheduled time:

```powershell
# Run monitor manually
python crawler_alert_monitor.py
```

You can also test with different scenarios:
- **Success**: Run when crawler just completed successfully
- **Failure**: Temporarily delete a database row to simulate missing data

## Notes

- ✅ Alerts are sent for **both success and failure** cases
- ✅ Monitor runs **5 minutes after crawler start** (4:35 PM Beijing)
- ✅ Uses **same Pacific Time logic** as crawler for date calculation
- ✅ Checks **log files** for error context
- ✅ Webhook URL is stored in `alert_config.json` (gitignored for security)

## Files

- `crawler_alert_monitor.py` - Main alert monitor script
- `alert_config.json` - Webhook URL configuration (gitignored)
- `crawler_alert_monitor.log` - Monitor execution logs
- `WECOM_WEBHOOK_SETUP.md` - Detailed WeCom setup guide
- `ALERT_MONITOR_README.md` - This file
