# SteamWorks Visualization Dashboard

## Overview

This visualization system provides daily monitoring and analysis of SteamWorks game metrics through interactive Plotly charts, automated data loading from MySQL, and email alerts for KPI anomalies.

## Features

- **Interactive Dashboard**: Jupyter notebook with Plotly charts for daily viewing
- **Automated Refresh**: Scheduled execution via Windows Task Scheduler
- **Email Alerts**: Automated notifications for data freshness and KPI anomalies
- **Export Capabilities**: Charts exportable as HTML (interactive) and PNG (for presentations)
- **Modular Design**: Reusable Python modules for easy extension

## Project Structure

```
Visualization/
├── dashboard.ipynb              # Main interactive dashboard
├── lib/
│   ├── __init__.py
│   ├── db_connector.py         # MySQL connection management
│   ├── data_loader.py          # SQL queries and data loading
│   ├── chart_builder.py        # Plotly chart creation
│   └── alert_engine.py         # Alert rules and email sender
├── alerts.py                    # Standalone alert execution script
├── refresh_dashboard.py         # Automated dashboard refresh script
├── exports/
│   └── charts/                 # Exported chart files
├── config/
│   └── env.example             # Environment variable template
├── requirements_visualization.txt
├── README.md                    # This file
└── AUTOMATION_SETUP.md         # Task Scheduler setup guide
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd Visualization
pip install -r requirements_visualization.txt
```

**Key packages:**
- `pandas` - Data manipulation
- `plotly` - Interactive charting
- `kaleido` - PNG/PDF export (required for PowerPoint exports)
- `sqlalchemy` - Database connection
- `papermill` - Automated notebook execution
- `python-dotenv` - Environment variable management

### 2. Configure Environment Variables

1. Copy the environment template:
   ```bash
   cp config/env.example config/.env
   ```

2. Edit `config/.env` with your credentials:
   ```
   # MySQL Database
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_DATABASE=steamworks_crawler
   MYSQL_USER=root
   MYSQL_PASSWORD=your_actual_password

   # SMTP Email (for alerts)
   SMTP_SERVER=smtp.exmail.qq.com
   SMTP_PORT=465
   SMTP_USER=your_email@company.com
   SMTP_PASSWORD=your_email_password
   ALERT_RECIPIENT=jimhanzhang@tencent.com
   ```

3. **Security Note**: The `.env` file is gitignored. Never commit credentials to version control.

### 3. Test the Setup

Test database connection:
```bash
python -m lib.db_connector
```

Test data loading:
```bash
python -m lib.data_loader
```

Test alert system:
```bash
python alerts.py
```

## Usage

### Interactive Dashboard (Manual)

1. Open Jupyter Lab:
   ```bash
   jupyter lab
   ```

2. Navigate to `dashboard.ipynb`

3. Run all cells (Shift + Enter or "Run All" from menu)

4. Charts are interactive - hover for details, zoom, pan, etc.

### Automated Dashboard Refresh

Run the refresh script (designed for Task Scheduler):
```bash
python refresh_dashboard.py
```

This will:
- Execute the notebook with fresh data
- Save timestamped output to `exports/dashboard_YYYYMMDD_HHMMSS.ipynb`
- Update `exports/dashboard_latest.ipynb`

### Alert System

Run the alert check script:
```bash
python alerts.py
```

This will:
- Check data freshness (latest stat_date vs expected date)
- Send consolidated email if alerts triggered
- Log results to `alerts.log`

### Exporting Charts

Charts are auto-exported when running the dashboard:
- **HTML files**: `exports/charts/dau_new_users_YYYYMMDD.html` (interactive, shareable)
- **PNG files**: `exports/charts/dau_new_users_YYYYMMDD.png` (for PowerPoint, 1920x1080)

Manual export from notebook:
```python
from lib.chart_builder import export_chart

export_chart(fig_dau, 'exports/charts/my_chart', format='both')
```

## Current Visualizations

### 1. DAU & New Users Trend (Dual-Axis Line Chart)
- **Left Y-axis**: Daily Active Users
- **Right Y-axis**: New Players
- **Breakdown**: By game (4 games, color-coded)
- **Time Range**: Oct 1, 2025 to present

### 2. Daily Revenue Trend (Stacked Area Chart)
- **Y-axis**: Daily Revenue ($)
- **Breakdown**: By game (stacked to show portfolio total)
- **Time Range**: Oct 1, 2025 to present

## Alert System

### Current Alerts

**Data Freshness Check**
- **Trigger**: Latest stat_date in database is older than yesterday
- **Action**: Email alert to jimhanzhang@tencent.com
- **Severity**: Warning

### Future Alerts (Planned)

- Retention drop >X%
- Revenue spike >Y%
- PCU/DAU anomaly
- Wishlist surge
- Specific game metric thresholds

## Automation

See [AUTOMATION_SETUP.md](AUTOMATION_SETUP.md) for Windows Task Scheduler configuration.

**Recommended Schedule:**
- **3:30 PM**: Crawler runs (existing)
- **3:45 PM**: Dashboard refresh (15-minute buffer)
- **3:50 PM**: Alert checks

## Customization

### Adding New Charts

1. Add data loading function to `lib/data_loader.py`:
   ```python
   def get_my_metric(start_date, end_date):
       # SQL query and DataFrame return
   ```

2. Add chart function to `lib/chart_builder.py`:
   ```python
   def create_my_chart(df):
       # Plotly figure creation
   ```

3. Add cells to `dashboard.ipynb`:
   ```python
   df_metric = get_my_metric(START_DATE, END_DATE)
   fig_metric = create_my_chart(df_metric)
   fig_metric.show()
   ```

### Adding New Alerts

1. Add check function to `lib/alert_engine.py`:
   ```python
   def check_my_kpi():
       # Return alert dict with 'alert_triggered', 'severity', 'message', 'details'
   ```

2. Add to `run_all_alerts()`:
   ```python
   alerts.append(check_my_kpi())
   ```

## Troubleshooting

### Database Connection Issues
- Verify MySQL is running
- Check credentials in `config/.env`
- Test with: `python -m lib.db_connector`

### PNG Export Fails
- Install kaleido: `pip install kaleido`
- Kaleido is required for static image exports

### Email Alerts Not Sending
- Verify SMTP credentials in `config/.env`
- Check firewall/network access to SMTP server
- Test with: `python alerts.py`

### Jupyter Kernel Issues
- Ensure virtual environment is activated
- Register kernel: `python -m ipykernel install --user --name=steamworks`
- Select correct kernel in Jupyter

## Logs

- `alerts.log` - Alert system execution log
- `refresh_dashboard.log` - Dashboard refresh execution log
- Application logs via Python logging module

## Support

For issues or questions:
1. Check logs for error details
2. Verify environment variables
3. Test individual components (db_connector, data_loader, etc.)
4. Review AUTOMATION_SETUP.md for scheduler issues

## Version History

- **v1.0** (2025-10-22): Initial release
  - DAU & New Users visualization
  - Revenue trend visualization
  - Data freshness alerts
  - Automated refresh system

