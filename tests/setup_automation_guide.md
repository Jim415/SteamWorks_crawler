# SteamWorks Crawler - Daily Automation Setup Guide

This guide explains how to set up the SteamWorks crawler to run automatically every day at 3:30 PM.

---

## Quick Setup (Automated - Recommended)

### **Step 1: Install tzdata (If Not Already Done)**
```powershell
pip install tzdata
```

### **Step 2: Run PowerShell Setup Script**

1. **Open PowerShell as Administrator:**
   - Press `Windows Key + X`
   - Select **"Windows PowerShell (Admin)"** or **"Terminal (Admin)"**

2. **Navigate to the project:**
   ```powershell
   cd D:\Steamworks_Crawler\SteamWorks_crawler
   ```

3. **Run the setup script:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File tests\setup_scheduled_task.ps1
   ```

4. **Follow the prompts** - the script will:
   - Create a Windows scheduled task
   - Configure it to run daily at 3:30 PM
   - Ask if you want to test it immediately

### **Step 3: Verify**

Open **Task Scheduler** (search in Start menu) and look for:
- Task Name: **SteamWorks_Crawler_Daily**
- Next Run Time: Should show next 3:30 PM

---

## Manual Setup (Alternative Method)

If you prefer to set up the task manually:

### **1. Open Task Scheduler**
- Press `Windows Key + R`
- Type: `taskschd.msc`
- Press Enter

### **2. Create Basic Task**
1. Click **"Create Basic Task"** in the right panel
2. Name: `SteamWorks_Crawler_Daily`
3. Description: `Runs the SteamWorks crawler daily at 3:30pm`
4. Click **Next**

### **3. Configure Trigger**
1. Select **"Daily"**
2. Click **Next**
3. Start date: Today's date
4. Start time: `15:30` (3:30 PM)
5. Recur every: `1 days`
6. Click **Next**

### **4. Configure Action**
1. Select **"Start a program"**
2. Click **Next**
3. Program/script: Browse to:
   ```
   D:\Steamworks_Crawler\SteamWorks_crawler\tests\run_crawler_scheduled.bat
   ```
4. Start in (optional): `D:\Steamworks_Crawler\SteamWorks_crawler`
5. Click **Next**

### **5. Finish Setup**
1. Review settings
2. Check **"Open the Properties dialog when I click Finish"**
3. Click **Finish**

### **6. Advanced Settings (in Properties dialog)**
1. Go to **"General"** tab:
   - Check: **"Run whether user is logged on or not"**
   - Check: **"Run with highest privileges"**

2. Go to **"Conditions"** tab:
   - Uncheck: **"Start the task only if the computer is on AC power"**
   - Check: **"Start the task if on battery power"**
   - Check: **"Wake the computer to run this task"** (optional)

3. Go to **"Settings"** tab:
   - Check: **"Allow task to be run on demand"**
   - Check: **"Run task as soon as possible after a scheduled start is missed"**
   - If task fails, restart every: `10 minutes`
   - Attempt to restart up to: `3 times`
   - Stop the task if it runs longer than: `2 hours`

4. Click **OK**
5. Enter your Windows password if prompted

---

## Testing the Automation

### **Test Immediately (Don't Wait for 3:30 PM)**

**Option 1: Via Task Scheduler**
1. Open Task Scheduler
2. Find **SteamWorks_Crawler_Daily**
3. Right-click → **Run**
4. Monitor: `D:\Steamworks_Crawler\SteamWorks_crawler\steamworks_crawler.log`

**Option 2: Via PowerShell**
```powershell
Start-ScheduledTask -TaskName "SteamWorks_Crawler_Daily"
```

**Option 3: Run Batch File Directly**
```powershell
cd D:\Steamworks_Crawler\SteamWorks_crawler\tests
.\run_crawler_scheduled.bat
```

---

## Monitoring & Logs

### **Log Files**
- **Main log:** `D:\Steamworks_Crawler\SteamWorks_crawler\steamworks_crawler.log`
- **Scheduled runs log:** `D:\Steamworks_Crawler\SteamWorks_crawler\scheduled_runs.log`

### **Check Last Run Status**

**Via PowerShell:**
```powershell
Get-ScheduledTask -TaskName "SteamWorks_Crawler_Daily" | Get-ScheduledTaskInfo
```

**Via Task Scheduler:**
1. Open Task Scheduler
2. Find **SteamWorks_Crawler_Daily**
3. Check **"Last Run Time"** and **"Last Run Result"**

---

## Troubleshooting

### **Task doesn't run at scheduled time**
1. Check if computer is on at 3:30 PM
2. Ensure "Wake computer to run" is enabled
3. Check Windows Event Viewer → Task Scheduler logs

### **Task runs but crawler fails**
1. Check `steamworks_crawler.log` for errors
2. Ensure `tzdata` is installed: `pip install tzdata`
3. Verify MySQL is running
4. Test manual run: `python steamworks_crawler.py`

### **MySQL connection fails**
1. Ensure MySQL service is running
2. Check database credentials in `steamworks_crawler.py`
3. Test connection: `python tests/test_setup.py`

### **Login required every time**
1. The crawler uses a persistent Chrome profile
2. After first manual login, it should remember credentials
3. Check `chrome_profile/` or `chrome_profile_clone/` directory exists

---

## Modifying the Schedule

### **Change Run Time**

**Via PowerShell:**
```powershell
$trigger = New-ScheduledTaskTrigger -Daily -At "16:00"  # Change to 4:00 PM
Set-ScheduledTask -TaskName "SteamWorks_Crawler_Daily" -Trigger $trigger
```

**Via Task Scheduler:**
1. Open Task Scheduler
2. Right-click task → **Properties**
3. Go to **Triggers** tab
4. Double-click the trigger
5. Change time
6. Click **OK**

### **Disable/Enable Task**

**Disable:**
```powershell
Disable-ScheduledTask -TaskName "SteamWorks_Crawler_Daily"
```

**Enable:**
```powershell
Enable-ScheduledTask -TaskName "SteamWorks_Crawler_Daily"
```

### **Delete Task**

**Via PowerShell:**
```powershell
Unregister-ScheduledTask -TaskName "SteamWorks_Crawler_Daily" -Confirm:$false
```

**Via Task Scheduler:**
1. Right-click task → **Delete**

---

## Important Notes

### **Timezone Considerations**
- The crawler collects "yesterday's" data based on Pacific Time
- Running at **3:30 PM Beijing Time** = **11:30 PM Pacific Time (previous day)**
- This ensures you get complete data for the previous day

### **First Run After Setup**
- You may need to manually log in to SteamWorks during the first automated run
- After that, the Chrome profile will remember your login
- Consider doing a test run while you're available to handle login

### **Network Requirements**
- Ensure stable internet connection
- The task is configured to only run if network is available

### **Computer Power State**
- Configure BIOS/Windows to wake from sleep at scheduled time (optional)
- Or keep computer running during scheduled time

---

## Support

If you encounter issues:
1. Check log files for error details
2. Run the test script: `python tests/test_setup.py`
3. Verify database connection and Chrome driver setup
4. Check Windows Event Viewer for Task Scheduler errors

---

**Created:** 2025-10-09  
**Last Updated:** 2025-10-09

