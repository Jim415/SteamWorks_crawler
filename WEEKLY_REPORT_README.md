# SteamWorks Weekly Report Generator

## Overview
This script generates a weekly Excel report for the 4 games you're tracking, with key metrics and week-over-week comparisons.

## Prerequisites
- Python 3.x
- MySQL database with `steamworks_crawler` database
- Required packages (install via `pip install -r requirements.txt`):
  - mysql-connector-python
  - openpyxl

## Usage

### Running the Script
```bash
python generate_weekly_report.py
```

The script will prompt you to enter a starting date (Monday) in YYYYMMDD format.

**Example:**
```
Enter the starting date (Monday) in YYYYMMDD format
Example: 20251006 for October 6, 2025
Start Date: 20251006
```

### Date Range Logic
- **Input:** Starting date (Monday) in YYYYMMDD format (e.g., `20251006`)
- **Current Week:** Input date + 6 days (7 days total: Oct 06-12, Mon-Sun)
- **Previous Week:** 7 days before input date (Sep 29 - Oct 05, Mon-Sun)

### Output
- **File Name:** `weekly_report_YYYYMMDD_to_YYYYMMDD.xlsx`
- **Example:** `weekly_report_20251006_to_20251012.xlsx`
- **Location:** Current directory

## Report Contents

The Excel report contains a single sheet with all 4 games in columns:

### Games Tracked
1. Delta Force (2507950)
2. Terminull Brigade (3104410)
3. Road to Empress (3478050)
4. Arena Breakout: Infinite (2073620)

### Metrics Per Game (6 columns each)

| Metric | Description | Format |
|--------|-------------|--------|
| **Sum New Players (WoW %)** | Total new players for the week with week-over-week % change | `1,234 (+5.2%)` |
| **Latest Unique Player** | Unique players on the last day of the week | `50,000.00` |
| **Sum Revenue (WoW %)** | Total revenue for the week with week-over-week % change | `$12,345.67 (+15.2%)` |
| **Lifetime Total Revenue** | Lifetime revenue on the last day of the week | `$500,000.00` |
| **Average DAU** | Average Daily Active Users for the week | `1,234.56` |
| **Median Playtime** | Median playtime on the last day of the week | `2 hours 15 minutes` |

### Formatting
- Numeric values: 2 decimal places
- Week-over-week changes: 1 decimal place with +/- sign
- If previous week = 0: Shows "N/A" for WoW change
- Game names: Merged header row with colored background
- All values: Centered alignment with borders

## Data Validation

The script validates that:
- All 4 games have complete data for ALL 14 days (current week + previous week)
- If ANY game is missing ANY day, the script will:
  - Terminate with an error
  - Report which game(s) and which date(s) are missing
  - Not generate a partial report

## Error Handling

### Missing Data Error Example
```
[ERROR] Cannot generate report due to missing data.
Missing data details:
  - Delta Force: Missing current week data for dates: 2025-10-10, 2025-10-11
  - Road to Empress: Missing previous week data for dates: 2025-09-29
```

### Other Errors
- Invalid date format: Script will show error and exit
- Database connection issues: Script will show database error
- Other unexpected errors: Full traceback will be displayed

## Logs
All operations are logged to: `weekly_report_generator.log`

## Typical Workflow

**Run on Monday night:**
```bash
python generate_weekly_report.py
# Enter: 20251006 (for the week starting Oct 6, 2025)
```

The script will:
1. Query data for Oct 06-12 (current week)
2. Query data for Sep 29 - Oct 05 (previous week)
3. Validate all data exists
4. Calculate metrics and WoW changes
5. Generate formatted Excel file
6. Output: `weekly_report_20251006_to_20251012.xlsx`

## Notes
- The script uses the same database credentials as your crawler scripts
- Make sure your daily crawler runs successfully before generating weekly reports
- The Excel file uses professional formatting with colored headers and borders
- All currency values are displayed with $ prefix and proper thousand separators




