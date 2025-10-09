# SteamWorks Historical Marketing Data Crawler

This script allows you to fetch historical marketing data for Delta Force over a 30-day period. It's perfect for analyzing the game's performance during any specific 30-day timeframe.

## Features

- **30-Day Data Extraction**: Automatically fetches exactly 30 days of marketing data
- **YYYYMMDD Date Format**: Simple date input format (e.g., 20241205)
- **Delta Force Only**: Focused on Delta Force game data
- **Game-Specific Storage**: Stores data only in `delta_force_daily_marketing` table
- **Same Data Structure**: Uses the same data extraction logic as the regular marketing crawler
- **Error Handling**: Continues processing even if some dates fail
- **Progress Tracking**: Shows progress and summary of successful/failed dates

## Files

- `steamworks_historical_marketing_crawler.py` - Main historical crawler class
- `run_historical_crawler.py` - Interactive configuration script
- `run_historical_crawler.bat` - Windows batch script
- `run_historical_crawler.sh` - Unix/Linux shell script
- `HISTORICAL_CRAWLER_README.md` - This documentation

## Usage

### Method 1: Interactive Script (Recommended)

```bash
python run_historical_crawler.py
```

This will:
1. Ask for start date in YYYYMMDD format (e.g., 20241205)
2. Automatically calculate end date (30 days later)
3. Show configuration and ask for confirmation
4. Run the crawler for exactly 30 days

### Method 2: Batch Files

**Windows:**
```bash
run_historical_crawler.bat
```

**Unix/Linux:**
```bash
./run_historical_crawler.sh
```

## Configuration Examples

### Delta Force Launch Period
```
Enter start date (YYYYMMDD format): 20241205
Start date: 2024-12-05
End date: 2025-01-03
Total days: 30
```

### Delta Force First Month
```
Enter start date (YYYYMMDD format): 20241205
Start date: 2024-12-05
End date: 2025-01-03
Total days: 30
```

### Any 30-Day Period
```
Enter start date (YYYYMMDD format): 20250101
Start date: 2025-01-01
End date: 2025-01-30
Total days: 30
```

## Data Structure

The historical crawler extracts the same data as the regular marketing crawler:

- **total_impressions**: Total impressions for the day
- **total_visits**: Total visits for the day
- **total_click_through_rate**: Overall click-through rate
- **owner_visits**: Percentage of visits from game owners
- **top_country_visits**: Top countries by visits
- **takeover_banner**: Takeover banner data (if above threshold)
- **main_cluster**: Main cluster aggregated data (if above threshold)
- **pop_up_message**: Pop-up message data (if above threshold)
- **all_source_breakdown**: Complete breakdown of all traffic sources
- **homepage_breakdown**: Complete breakdown of homepage traffic sources

## Database Storage

Data is stored **only** in the game-specific table:
- `delta_force_daily_marketing` - Delta Force specific table

Each record includes:
- `steam_app_id`: 2507950 (Delta Force)
- `game_name`: 'Delta Force'
- `stat_date`: The specific date for this data
- All marketing metrics as JSON fields

**Note**: Data is NOT stored in the overall `game_daily_marketing` table.

## Logging

The crawler creates detailed logs in `steamworks_historical_marketing_crawler.log` including:
- Progress for each date processed
- Success/failure status for each date
- Data extraction details
- Database storage confirmations
- Error messages and debugging information

## Error Handling

The crawler is designed to be resilient:
- If a date fails, it continues with the next date
- Provides summary of successful vs failed dates
- Logs all errors for debugging
- Uses database transactions to ensure data integrity

## Performance Considerations

- **Rate Limiting**: 2-second delay between date requests to be respectful
- **Memory Usage**: Processes one date at a time to manage memory
- **Database Efficiency**: Uses batch operations and proper indexing
- **Chrome Profile**: Reuses the same Chrome profile for all requests

## Troubleshooting

### Common Issues

1. **Login Required**: Make sure you're logged into SteamWorks in Chrome
2. **Invalid Date Format**: Use YYYYMMDD format (8 digits, no separators)
3. **Network Issues**: Check internet connection and SteamWorks availability
4. **Database Connection**: Verify database credentials and connectivity

### Debugging

Check the log file for detailed error information:
```bash
tail -f steamworks_historical_marketing_crawler.log
```

## Requirements

- Python 3.7+
- Selenium
- Chrome browser
- MySQL database
- All dependencies from the main marketing crawler

## Notes

- The crawler uses the same Chrome profile as the regular marketing crawler
- Data is stored with the actual date, not the current date
- Duplicate dates are handled with ON DUPLICATE KEY UPDATE
- The crawler respects the same threshold checks as the regular crawler
- Exactly 30 days of data will be fetched and stored

