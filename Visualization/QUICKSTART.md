# Quick Start Guide

## First-Time Setup (5 minutes)

### 1. Install Dependencies

```bash
cd Visualization
pip install -r requirements_visualization.txt
```

### 2. Configure Database Connection

Copy and edit the environment file:
```bash
# Copy template
cp config/env.example config/.env

# Edit with your actual credentials
# Use any text editor to update config/.env
```

**Required settings in `config/.env`:**
```
MYSQL_USER=root
MYSQL_PASSWORD=Zh1149191843!
ALERT_RECIPIENT=jimhanzhang@tencent.com
```

### 3. Test Connection

```bash
python -m lib.db_connector
```

Expected output:
```
✓ Connection successful!
```

### 4. Run the Dashboard

```bash
jupyter lab
```

Then open `dashboard.ipynb` and run all cells (Shift + Enter or "Run All")

## Daily Usage

### View Dashboard
```bash
cd Visualization
jupyter lab
# Open dashboard.ipynb and run all cells
```

### Run Alerts Manually
```bash
cd Visualization
python alerts.py
```

### Automated Execution

See [AUTOMATION_SETUP.md](AUTOMATION_SETUP.md) for Task Scheduler configuration.

## Troubleshooting

**"No module named 'lib'"**
- Make sure you're running from the Visualization directory
- Check that lib/__init__.py exists

**"MYSQL_USER environment variable is required"**
- Create `config/.env` file from `config/env.example`
- Add your database credentials

**"PNG export failed"**
- Install kaleido: `pip install kaleido`

**Database connection failed**
- Verify MySQL is running
- Check credentials in `config/.env`
- Test with: `python -m lib.db_connector`

## What You Get

✅ **2 Interactive Charts:**
- DAU & New Users (dual-axis line chart)
- Daily Revenue (stacked area chart)

✅ **Automated Exports:**
- HTML files (interactive, shareable)
- PNG files (for PowerPoint, 1920x1080)

✅ **Email Alerts:**
- Data freshness monitoring
- Sent to jimhanzhang@tencent.com

✅ **Scheduled Automation:**
- Daily refresh at 3:45 PM
- Alert checks at 3:50 PM

## Next Steps

1. **Test the dashboard** - Run manually first
2. **Verify alerts** - Run `python alerts.py`
3. **Setup automation** - Follow AUTOMATION_SETUP.md
4. **Add more charts** - See README.md for customization guide

## Support

- Full documentation: [README.md](README.md)
- Automation guide: [AUTOMATION_SETUP.md](AUTOMATION_SETUP.md)
- Check logs: `alerts.log`, `refresh_dashboard.log`

