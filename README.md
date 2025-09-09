# SteamWorks Crawler - Production Version

A fully automated web crawler for extracting daily game data from SteamWorks portal and storing it in a MySQL database.

## Overview

This crawler automates the daily manual task of fetching game data for "Terminull Brigade" from SteamWorks portal. It extracts data from 7 different pages and stores 16+ data points in a MySQL database.

## Features

✅ **Complete 7-Page Coverage:**
- Default Game Page (3 data points)
- Lifetime Play Time Page (1 data point)
- Wishlist Page (2 data points)
- Players Page (3 data points)
- Regions Revenue Page (1 data point)
- Downloads Region Page (2 data points)
- In-Game Purchases Page (2 data points)

✅ **Robust Authentication:**
- Manual login prompt for 2FA bypass
- Session management
- Automatic re-navigation after login

✅ **Data Extraction:**
- 16+ data points extracted daily
- Complex table parsing
- JSON formatting for structured data
- Regional breakdowns (top 10 countries/regions)

✅ **Database Integration:**
- MySQL database storage
- Automatic date-based deduplication
- Comprehensive error handling

## Data Points Extracted

### Default Game Page
- **Lifetime Unique Users**: Total unique users who have played the game
- **Median Playtime**: Median time played in minutes
- **Total Revenue**: Lifetime Steam revenue (gross)

### Lifetime Play Time Page
- **Playtime Breakdown**: JSON with 9 time brackets and percentages

### Wishlist Page
- **Wishlist Additions**: Total wishlist additions
- **Outstanding Wishes**: Current outstanding wishlist count

### Players Page
- **Daily Active Users**: Maximum daily active users
- **Peak Concurrent Users**: Maximum daily peak concurrent users
- **Regional Players**: Top 10 countries with player percentages

### Regions Revenue Page
- **Regional Revenue**: Top 10 countries with revenue percentages + World total

### Downloads Region Page
- **Total Downloads**: Total download count
- **Regional Downloads**: Top 10 regions with download percentages

### In-Game Purchases Page
- **Daily Revenue**: Revenue for the selected period
- **In-Game Breakdown**: JSON with 26+ items, IDs, prices, and revenue

## Installation

### Prerequisites
- Python 3.8+
- MySQL Server
- Chrome Browser

### Setup

1. **Clone/Download the project**
2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup MySQL database:**
   ```bash
   mysql -u root -p < setup_database.sql
   ```

5. **Configure database connection:**
   - Update `test_database.py` with your MySQL credentials
   - Test connection: `python test_database.py`

## Usage

### Daily Run
```bash
python steamworks_crawler.py
```

### Check Database
```bash
python check_database.py
```

## How It Works

1. **Authentication**: Opens Chrome with temporary profile, prompts for manual login
2. **Navigation**: Visits each of the 7 SteamWorks pages sequentially
3. **Data Extraction**: Uses XPath selectors to extract specific data points
4. **Time Filtering**: Automatically sets "yesterday" filter where needed
5. **Database Storage**: Saves all data with date-based deduplication
6. **Error Handling**: Continues processing even if individual data points fail

## File Structure

```
SteamWorks_crawler/
├── steamworks_crawler.py      # Main crawler script
├── requirements.txt           # Python dependencies
├── setup_database.sql         # Database setup script
├── test_database.py           # Database connection test
├── check_database.py          # Database data verification
├── steamworks_poc.py          # Proof of concept (legacy)
├── README.md                  # This file
└── venv/                      # Virtual environment
```

## Database Schema

Database: `steamworks_crawler`

Table: `game_daily_metrics` (one row per Steam app per Pacific date)

- Primary key: (`steam_app_id`, `stat_date`)
- Currency: USD
- Date rule: `stat_date` is the Pacific Time date that just ended when the crawler runs (e.g., run at 15:30 Beijing ≈ 00:30 PT on 2025-01-10 → `stat_date` = 2025-01-09).
- JSON columns are native JSON; ETL provides pre-shaped structures.

Columns

- Identifiers & metadata
  - `steam_app_id` INT UNSIGNED NOT NULL
  - `game_name` VARCHAR(255) NULL
  - `stat_date` DATE NOT NULL
  - `notes` VARCHAR(255) NULL
- Core activity
  - `dau` INT UNSIGNED NULL
  - `pcu` INT UNSIGNED NULL
  - `new_players` INT UNSIGNED NULL
  - `total_downloads` INT UNSIGNED NULL
  - `pcu_over_dau` DECIMAL(8,4) NULL
  - `players_20h_plus` INT UNSIGNED NULL
  - `unique_player` INT UNSIGNED NULL
- Playtime (seconds)
  - `median_playtime` VARCHAR(255) NULL
  - `avg_playtime` VARCHAR(255) NULL
- Retention & mix (precomputed)
  - `d1_retention` DECIMAL(8,4) NULL
  - `new_vs_returning_ratio` DECIMAL(8,4) NULL
- Revenue (USD)
  - `daily_total_revenue` DECIMAL(14,2) NULL
  - `lifetime_total_revenue` DECIMAL(14,2) NULL
  - `daily_arpu` DECIMAL(12,6) NULL
  - `top3_iap_share` DECIMAL(8,4) NULL
- Wishlist
  - `wishlist` INT UNSIGNED NULL
  - `wishlist_additions` INT UNSIGNED NULL
  - `wishlist_deletions` INT UNSIGNED NULL
  - `wishlist_conversions` INT UNSIGNED NULL
  - `wishlist_outstanding` INT UNSIGNED NULL
  - `lifetime_wishlist_conversion_rate` DECIMAL(8,4) NULL
- Geo & IAP (JSON arrays)
  - `top10_country_dau` JSON NULL
  - `top10_country_downloads` JSON NULL
  - `top10_region_downloads` JSON NULL
  - `top10_country_revenue` JSON NULL
  - `top10_region_revenue` JSON NULL
  - `top10_country_arpu` JSON NULL
  - `top10_region_arpu` JSON NULL
  - `iap_breakdown_json` JSON NULL

JSON shapes (examples)

- `top10_country_dau`:
  ```json
  [{"country":"US","players":12345,"share":0.2345,"rank":1}]
  ```
- `top10_country_downloads`:
  ```json
  [{"country":"US","downloads":12345,"share":0.2345,"rank":1}]
  ```
- `top10_region_downloads`:
  ```json
  [{"region":"NA","downloads":12345,"share":0.2345,"rank":1}]
  ```
- `top10_country_revenue`:
  ```json
  [{"country":"US","revenue":12345.67,"share":0.2345,"rank":1}]
  ```
- `top10_region_revenue`:
  ```json
  [{"region":"NA","revenue":12345.67,"share":0.2345,"rank":1}]
  ```
- `top10_country_arpu`:
  ```json
  [{"country":"US","arpu":1.234567,"rank":1}]
  ```
- `top10_region_arpu`:
  ```json
  [{"region":"NA","arpu":1.234567,"rank":1}]
  ```
- `iap_breakdown_json`:
  ```json
  [{"item":"Starter Pack","id":"sku123","units":1000,"avg_price":1.99,"revenue":1990.00}]
  ```

## Error Handling

- **Page Load Failures**: Continues to next page
- **Data Extraction Failures**: Logs warning, continues processing
- **Database Errors**: Logs error, continues with other data
- **Authentication Issues**: Prompts for manual login
- **Network Issues**: Automatic retry mechanisms

## Logging

Comprehensive logging to `steamworks_crawler.log`:
- INFO: Successful operations
- WARNING: Failed data extractions
- ERROR: Critical failures

## Production Deployment

### Automated Daily Run
Set up a cron job or scheduler:

```bash
# Add to crontab for daily run at 9 AM
0 9 * * * cd /path/to/SteamWorks_crawler && source venv/bin/activate && python steamworks_crawler.py
```

### Monitoring
- Check log files regularly
- Monitor database for new entries
- Set up alerts for failed runs

## Troubleshooting

### Common Issues

1. **Chrome Driver Issues**
   - Ensure Chrome is installed and up to date
   - Check ChromeDriver compatibility

2. **Database Connection**
   - Verify MySQL credentials in `test_database.py`
   - Ensure MySQL service is running

3. **Login Issues**
   - Follow manual login prompt
   - Ensure SteamWorks access is active

4. **Data Extraction Failures**
   - Check SteamWorks page structure changes
   - Review logs for specific failures

### Support
For issues or questions, check the logs and ensure all prerequisites are met.

## Version History

- **v1.0** (Current): Production-ready crawler with all 7 pages and 16+ data points
- Complete error handling and database integration
- Manual login authentication system
- Comprehensive logging and monitoring

---

**Note**: This crawler is designed for the specific SteamWorks portal structure for "Terminull Brigade". Page structure changes may require selector updates. 