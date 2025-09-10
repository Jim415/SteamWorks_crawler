# SteamWorks Crawler - Field Documentation

## Overview
This document describes all fields extracted by the SteamWorks crawler, including their sources, destinations, and data types. The crawler processes three games: Delta Force (2507950), Terminull Brigade (3104410), and Road to Empress (3478050).

## Database Destination
All data is stored in the MySQL table `game_daily_metrics` with the following key structure:
- **Primary Key**: `steam_app_id` + `stat_date` (Pacific timezone, yesterday's date)
- **Data Type**: Most numeric fields are stored as integers or floats, complex data as JSON strings

---

## Field Categories

### 1. Basic Game Information

#### `steam_app_id` (INTEGER)
- **Source**: Hardcoded in crawler configuration
- **Destination**: `game_daily_metrics.steam_app_id`
- **Description**: Unique Steam application identifier for each game
- **Values**: 2507950 (Delta Force), 3104410 (Terminull Brigade), 3478050 (Road to Empress)

#### `game_name` (VARCHAR)
- **Source**: Hardcoded in crawler configuration
- **Destination**: `game_daily_metrics.game_name`
- **Description**: Human-readable name of the game
- **Values**: "Delta Force", "Terminull Brigade", "Road to Empress"

#### `stat_date` (DATE)
- **Source**: Calculated as Pacific timezone yesterday
- **Destination**: `game_daily_metrics.stat_date`
- **Description**: Date for which the statistics are collected (always yesterday in Pacific time)

---

### 2. Player Metrics (from Default Game Page)

#### `unique_player` (INTEGER)
- **Source**: Default Game Page → "Lifetime unique users" field
- **Destination**: `game_daily_metrics.unique_player`
- **Description**: Total number of unique players who have ever played the game
- **Page**: https://partner.steampowered.com/app/details/{app_id}/
- **Location**: Main statistics table, "Lifetime unique users" row

#### `lifetime_total_units` (INTEGER)
- **Source**: Default Game Page → "Lifetime total units" field
- **Destination**: `game_daily_metrics.lifetime_total_units`
- **Description**: Total number of game units sold/downloaded since launch
- **Page**: https://partner.steampowered.com/app/details/{app_id}/
- **Location**: Main statistics table, "Lifetime total units" row

#### `lifetime_total_revenue` (INTEGER)
- **Source**: Default Game Page → "Lifetime Steam revenue (gross)" field
- **Destination**: `game_daily_metrics.lifetime_total_revenue`
- **Description**: Total revenue earned from Steam sales (gross amount before Steam's cut)
- **Page**: https://partner.steampowered.com/app/details/{app_id}/
- **Location**: Main statistics table, "Lifetime Steam revenue (gross)" row

#### `wishlist` (INTEGER)
- **Source**: Default Game Page → "Wishlists" field
- **Destination**: `game_daily_metrics.wishlist`
- **Description**: Current number of outstanding wishlist entries
- **Page**: https://partner.steampowered.com/app/details/{app_id}/
- **Location**: Main statistics table, "Wishlists" row

#### `median_playtime` (VARCHAR)
- **Source**: Default Game Page → "Median time played" field
- **Destination**: `game_daily_metrics.median_playtime`
- **Description**: Median playtime across all players (e.g., "3 hours 13 minutes")
- **Page**: https://partner.steampowered.com/app/details/{app_id}/
- **Location**: Main statistics table, "Median time played" row

---

### 3. Playtime Analysis (from Lifetime Play Time Page)

#### `players_20h_plus` (INTEGER)
- **Source**: Lifetime Play Time Page → Playtime breakdown table
- **Destination**: `game_daily_metrics.players_20h_plus`
- **Description**: Percentage of players who have played 20+ hours
- **Page**: https://partner.steampowered.com/app/playtime/{app_id}/
- **Location**: Playtime breakdown table, "20 hours" row percentage

#### `avg_playtime` (VARCHAR)
- **Source**: Lifetime Play Time Page → Average time played field
- **Destination**: `game_daily_metrics.avg_playtime`
- **Description**: Average playtime across all players (e.g., "35 hours 11 minutes")
- **Page**: https://partner.steampowered.com/app/playtime/{app_id}/
- **Location**: Statistics section, "Average time played" row

---

### 4. Daily Player Activity (from Players Page)

#### `dau` (INTEGER)
- **Source**: Players Page → "Maximum daily active users" field (yesterday filter)
- **Destination**: `game_daily_metrics.dau`
- **Description**: Number of unique players who played the game yesterday
- **Page**: https://partner.steampowered.com/app/players/{app_id}/
- **Location**: Main statistics table, "Maximum daily active users" row
- **Note**: Time filter set to "yesterday"

#### `pcu` (INTEGER)
- **Source**: Players Page → "Maximum daily peak concurrent users" field (yesterday filter)
- **Destination**: `game_daily_metrics.pcu`
- **Description**: Peak number of players simultaneously online yesterday
- **Page**: https://partner.steampowered.com/app/players/{app_id}/
- **Location**: Main statistics table, "Maximum daily peak concurrent users" row
- **Note**: Time filter set to "yesterday"

#### `pcu_over_dau` (DECIMAL)
- **Source**: Calculated from `pcu` ÷ `dau`
- **Destination**: `game_daily_metrics.pcu_over_dau`
- **Description**: Ratio of peak concurrent users to daily active users
- **Calculation**: Automatically computed during data processing

#### `new_players` (INTEGER)
- **Source**: Calculated from difference in `unique_player` between yesterday and day before
- **Destination**: `game_daily_metrics.new_players`
- **Description**: Number of new players who played the game for the first time yesterday
- **Calculation**: `unique_player(today) - unique_player(yesterday)`

#### `d1_retention` (DECIMAL)
- **Source**: Calculated from `(dau - new_players) ÷ dau(yesterday)`
- **Destination**: `game_daily_metrics.d1_retention`
- **Description**: Percentage of yesterday's players who returned today
- **Calculation**: `(today_dau - new_players) ÷ yesterday_dau`

#### `new_vs_returning_ratio` (DECIMAL)
- **Source**: Calculated from `new_players ÷ (dau - new_players)`
- **Destination**: `game_daily_metrics.new_vs_returning_ratio`
- **Description**: Ratio of new players to returning players
- **Calculation**: `new_players ÷ returning_players`

---

### 5. Daily Revenue & Sales (from Regions and Countries Revenue Page)

#### `daily_total_revenue` (DECIMAL)
- **Source**: Regions and Countries Revenue Page → World table → Revenue row (yesterday filter)
- **Destination**: `game_daily_metrics.daily_total_revenue`
- **Description**: Total revenue earned from Steam sales yesterday
- **Page**: https://partner.steampowered.com/region/?&appID={app_id}
- **Location**: World section table, "Revenue" row
- **Note**: Time filter set to "yesterday"

#### `daily_units` (INTEGER)
- **Source**: Regions and Countries Revenue Page → World table → Units row (yesterday filter)
- **Destination**: `game_daily_metrics.daily_units`
- **Description**: Number of game units sold/downloaded yesterday
- **Page**: https://partner.steampowered.com/region/?&appID={app_id}
- **Location**: World section table, "Units" row
- **Note**: Time filter set to "yesterday"

#### `daily_arpu` (DECIMAL)
- **Source**: Calculated from `daily_total_revenue ÷ dau`
- **Destination**: `game_daily_metrics.daily_arpu`
- **Description**: Average revenue per user yesterday
- **Calculation**: `daily_total_revenue ÷ dau`

---

### 6. Wishlist Activity (from Wishlist Page)

#### `wishlist_additions` (INTEGER)
- **Source**: Wishlist Page → "Wishlist Action Summary" table → Additions row (yesterday filter)
- **Destination**: `game_daily_metrics.wishlist_additions`
- **Description**: Number of wishlist additions yesterday
- **Page**: https://partner.steampowered.com/app/wishlist/{app_id}/
- **Location**: "Wishlist Action Summary, yesterday" table, "Wishlist additions" row
- **Note**: Time filter set to "yesterday"

#### `wishlist_deletions` (INTEGER)
- **Source**: Wishlist Page → "Wishlist Action Summary" table → Deletions row (yesterday filter)
- **Destination**: `game_daily_metrics.wishlist_deletions`
- **Description**: Number of wishlist deletions yesterday
- **Page**: https://partner.steampowered.com/app/wishlist/{app_id}/
- **Location**: "Wishlist Action Summary, yesterday" table, "Wishlist deletions" row
- **Note**: Time filter set to "yesterday"

#### `wishlist_conversions` (INTEGER)
- **Source**: Wishlist Page → "Wishlist Action Summary" table → Purchases & Activations row (yesterday filter)
- **Destination**: `game_daily_metrics.wishlist_conversions`
- **Description**: Number of wishlist purchases and activations yesterday
- **Page**: https://partner.steampowered.com/app/wishlist/{app_id}/
- **Location**: "Wishlist Action Summary, yesterday" table, "Wishlist purchases & activations" row
- **Note**: Time filter set to "yesterday"

#### `lifetime_wishlist_conversion_rate` (DECIMAL)
- **Source**: Wishlist Page → "Lifetime Conversion Rate" field
- **Destination**: `game_daily_metrics.lifetime_wishlist_conversion_rate`
- **Description**: Lifetime percentage of wishlist entries that converted to purchases
- **Page**: https://partner.steampowered.com/app/wishlist/{app_id}/
- **Location**: Statistics section, "Lifetime Conversion Rate" row

---

### 7. Download Activity (from Downloads by Region Page)

#### `total_downloads` (INTEGER)
- **Source**: Downloads by Region Page → "Total Downloads" field (yesterday filter)
- **Destination**: `game_daily_metrics.total_downloads`
- **Description**: Total number of game downloads yesterday
- **Page**: https://partner.steampowered.com/nav_regions.php?downloads=1&appID={app_id}
- **Location**: Main statistics section, "Total Downloads" field
- **Note**: Time filter set to "yesterday"

---

### 8. In-Game Purchases (from In-Game Purchases Page)

#### `top3_iap_share` (DECIMAL)
- **Source**: In-Game Purchases Page → Item Breakdown table
- **Destination**: `game_daily_metrics.top3_iap_share`
- **Description**: Percentage of total IAP revenue generated by top 3 items
- **Page**: https://partner.steampowered.com/app/microtxn/{app_id}/
- **Location**: "Item Breakdown" table, calculated from top 3 items
- **Note**: Time filter set to "yesterday"

---

### 9. Geographic Data (JSON Fields)

#### `top10_country_dau` (JSON)
- **Source**: Players Page → Country table (yesterday filter)
- **Destination**: `game_daily_metrics.top10_country_dau`
- **Description**: Top 10 countries by percentage of daily active users
- **Page**: https://partner.steampowered.com/app/players/{app_id}/
- **Location**: Country table with headers "Country" and "% of Players"
- **JSON Structure**: Array of objects with:
  - `country`: Country name
  - `share`: Percentage as string (e.g., "15.23%")
  - `rank`: Ranking position (1-10)
  - `players`: Calculated number of players based on DAU

#### `top10_country_revenue` (JSON)
- **Source**: Regions and Countries Revenue Page → Countries table (yesterday filter)
- **Destination**: `game_daily_metrics.top10_country_revenue`
- **Description**: Top 10 countries by revenue yesterday
- **Page**: https://partner.steampowered.com/region/?&appID={app_id}
- **Location**: Countries section table
- **JSON Structure**: Array of objects with:
  - `country`: Country name
  - `share`: Revenue percentage as string (e.g., "25.67%")
  - `rank`: Ranking position (1-10)
  - `revenue`: Revenue amount as number
  - `units`: Number of units sold
  - `change_vs_prior`: Change percentage vs previous period
  - `arpu`: Average revenue per user (calculated from country DAU data)

#### `top10_region_revenue` (JSON)
- **Source**: Regions and Countries Revenue Page → Regions table (yesterday filter)
- **Destination**: `game_daily_metrics.top10_region_revenue`
- **Description**: Top 10 regions by revenue yesterday
- **Page**: https://partner.steampowered.com/region/?&appID={app_id}
- **Location**: Regions section table
- **JSON Structure**: Array of objects with:
  - `region`: Region name
  - `share`: Revenue percentage as string (e.g., "45.12%")
  - `rank`: Ranking position (1-10)
  - `revenue`: Revenue amount as number
  - `units`: Number of units sold
  - `change_vs_prior`: Change percentage vs previous period

#### `top10_country_downloads` (JSON)
- **Source**: Downloads by Region Page → Country table (yesterday filter)
- **Destination**: `game_daily_metrics.top10_country_downloads`
- **Description**: Top 10 countries by downloads yesterday
- **Page**: https://partner.steampowered.com/nav_regions.php?downloads=1&appID={app_id}
- **Location**: Country table with headers "Country", "Total downloads", "Share"
- **JSON Structure**: Array of objects with:
  - `country`: Country name
  - `downloads`: Number of downloads
  - `share`: Download percentage as string (e.g., "12.34%")
  - `rank`: Ranking position (1-10)

#### `top10_region_downloads` (JSON)
- **Source**: Downloads by Region Page → Region table (yesterday filter)
- **Destination**: `game_daily_metrics.top10_region_downloads`
- **Description**: Top 10 regions by downloads yesterday
- **Page**: https://partner.steampowered.com/nav_regions.php?downloads=1&appID={app_id}
- **Location**: Region table with headers "Region", "Total downloads", "Share"
- **JSON Structure**: Array of objects with:
  - `region`: Region name
  - `downloads`: Number of downloads
  - `share`: Download percentage as string (e.g., "28.45%")
  - `rank`: Ranking position (1-10)

#### `iap_breakdown_json` (JSON)
- **Source**: In-Game Purchases Page → Item Breakdown table (yesterday filter)
- **Destination**: `game_daily_metrics.iap_breakdown_json`
- **Description**: Detailed breakdown of in-game purchase items
- **Page**: https://partner.steampowered.com/app/microtxn/{app_id}/
- **Location**: "Item Breakdown" table
- **JSON Structure**: Array of objects with:
  - `item`: Item name
  - `id`: Item ID
  - `units`: Number of units sold
  - `average_price`: Average price per unit
  - `revenue`: Total revenue from this item
  - `rank`: Ranking by revenue (1-N)

---

## Data Processing Notes

### Time Zone Handling
- All dates are calculated in Pacific timezone (America/Los_Angeles)
- `stat_date` is always set to yesterday in Pacific time
- All "yesterday" filters refer to Pacific timezone yesterday

### Data Validation
- Numeric values are parsed and cleaned (removing commas, currency symbols, etc.)
- Missing or invalid data is stored as NULL in the database
- JSON fields are validated and formatted consistently

### Error Handling
- If a page requires manual login, the crawler pauses and waits for user intervention
- Failed extractions are logged but don't stop the entire process
- Database operations use INSERT...ON DUPLICATE KEY UPDATE to handle re-runs

### Cron Schedule
- The crawler runs daily at 3:15 PM Pacific time
- Each run processes all three games sequentially
- Data is stored with yesterday's date as the stat_date

---

## Technical Implementation

### Browser Automation
- Uses Selenium WebDriver with Chrome
- Maintains persistent login sessions via Chrome profile
- Handles Steam Guard authentication automatically

### Database Schema
- Primary key: `(steam_app_id, stat_date)`
- Supports duplicate key updates for re-running crawls
- JSON fields stored as TEXT with proper JSON formatting

### Logging
- Comprehensive logging to `steamworks_crawler.log`
- Cron execution logs to `cron.log`
- Error tracking and debugging information included
