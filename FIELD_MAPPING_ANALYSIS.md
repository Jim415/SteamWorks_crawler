# Database Field Mapping Analysis

## Complete Field Mapping Table

| Field Name | Type | Steamworks Source Page | Calculation Method |
|------------|------|------------------------|---------------------|
| `stat_date` | DATE | System Generated | Calculated as Pacific Time "yesterday" when crawler runs. Uses `datetime.now(ZoneInfo('America/Los_Angeles')) - timedelta(days=1)` |
| `game_name` | VARCHAR(255) | Input Parameter | Passed as parameter to crawler constructor |
| `steam_app_id` | INT UNSIGNED | Input Parameter | Passed as parameter to crawler constructor |
| `dau` | INT UNSIGNED | Players Page | Extracted from "Maximum daily active users" field. XPath: `//td[contains(text(), 'Maximum daily active users')]/following-sibling::td[@align='right']` |
| `pcu` | INT UNSIGNED | Players Page | Extracted from "Maximum daily peak concurrent users" field. XPath: `//td[contains(text(), 'Maximum daily peak concurrent users')]/following-sibling::td[@align='right']` |
| `unique_player` | INT UNSIGNED | Default Game Page | Extracted from "Lifetime unique users" field. XPath: `//td[contains(text(), 'Lifetime unique users')]/following-sibling::td[@align='right']`. **Critical field** - extraction failure returns None |
| `new_players` | INT UNSIGNED | Calculated | `unique_player_today - unique_player_yesterday` (from database lookup). If yesterday's value is NULL, uses today's unique_player. Minimum value is 0 (no negative deltas) |
| `total_downloads` | INT UNSIGNED | Downloads by Region Page | Extracted from "Total Downloads" field. XPath: `//div[contains(text(), 'Total Downloads:')]` or `//td[contains(text(), 'Total Downloads')]/following-sibling::td`. Requires "yesterday" date filter |
| `d1_retention` | DECIMAL(8,4) | Calculated | `(today_dau - today_new_players) / yesterday_dau`. Requires both today's DAU and yesterday's DAU from database. Returns NULL if yesterday_dau is NULL or 0 |
| `pcu_over_dau` | DECIMAL(8,4) | Calculated | `pcu / dau` (rounded to 2 decimals). Returns NULL if dau is NULL or 0 |
| `new_vs_returning_ratio` | DECIMAL(8,4) | Calculated | `new_players / (dau - new_players)` (rounded to 2 decimals). Returns NULL if returning players (dau - new_players) <= 0 |
| `median_playtime` | VARCHAR(255) | Default Game Page OR Lifetime Play Time Page | **Primary source**: Default Game Page - XPath: `//td[contains(text(), 'Median time played')]/following-sibling::td[@align='right']`. **Fallback**: Lifetime Play Time Page - XPath: `//td[b[contains(text(), 'Median time played')]]/following-sibling::td`. Stored as string (e.g., "3 hours 9 minutes") |
| `avg_playtime` | VARCHAR(255) | Lifetime Play Time Page | Extracted from "Average time played" field. XPath: `//td[b[contains(text(), 'Average time played')]]/following-sibling::td`. Stored as string |
| `players_20h_plus` | INT UNSIGNED | Lifetime Play Time Page | Extracted from Playtime Breakdown Table - percentage of users with "20 hours" or more playtime. Parsed as integer percentage |
| `lifetime_total_revenue` | DECIMAL(14,2) | Default Game Page | Extracted from "Lifetime Steam revenue (gross)" field. XPath: `//td[normalize-space(text())='Lifetime Steam revenue (gross)']/following-sibling::td[@align='right']`. Parsed from currency format (e.g., "$56,289,662") |
| `daily_total_revenue` | DECIMAL(14,2) | Regions and Countries Revenue Page | Extracted from World table → "Revenue" row. Requires "yesterday" date filter. XPath: Finds World header, then searches rows for label="revenue" |
| `lifetime_total_units` | INT | Default Game Page | Extracted from "Lifetime total units" field. XPath: `//td[contains(text(), 'Lifetime total units')]/following-sibling::td[@align='right']` |
| `daily_units` | INT | Regions and Countries Revenue Page | Extracted from World table → "Units" row. Requires "yesterday" date filter. XPath: Finds World header, then searches rows for label="units" |
| `daily_arpu` | DECIMAL(12,6) | Calculated | `daily_total_revenue / dau` (rounded to 2 decimals). Returns NULL if dau is NULL or 0 |
| `top3_iap_share` | DECIMAL(8,4) | In-Game Purchases Page | Calculated from IAP breakdown: `sum(top3_revenue) / sum(all_revenue)` (rounded to 4 decimals). Requires "yesterday" date filter |
| `wishlist` | INT UNSIGNED | Default Game Page | Extracted from "Wishlists" (Outstanding count) field. XPath: `//td[normalize-space(text())='Wishlists']/following-sibling::td`. Value may include trailing '+' link, so first token is extracted |
| `lifetime_wishlist_conversion_rate` | DECIMAL(8,4) | Wishlist Page | Extracted from "Lifetime Conversion Rate" field. XPath: `//td[contains(text(), 'Lifetime Conversion Rate')]/following-sibling::td`. No date filter required (lifetime metric) |
| `wishlist_additions` | INT UNSIGNED | Wishlist Page | Extracted from "Wishlist Action Summary, yesterday" table → "Wishlist additions" row. Requires "yesterday" date filter. XPath: `//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'wishlist action summary')]/following::table[1]//tr[td]` |
| `wishlist_deletions` | INT UNSIGNED | Wishlist Page | Extracted from "Wishlist Action Summary, yesterday" table → "Wishlist deletions" row. Requires "yesterday" date filter |
| `wishlist_conversions` | INT UNSIGNED | Wishlist Page | Extracted from "Wishlist Action Summary, yesterday" table → "Wishlist purchases & activations" row. Requires "yesterday" date filter |
| `top10_country_dau` | JSON | Players Page | Extracted from Country table with headers "Country" and "% of Players". Requires "yesterday" date filter. JSON structure: `[{"country": "US", "share": "50.00%", "rank": 1, "players": 12345}, ...]`. Players calculated from `dau * (share_percentage / 100)` |
| `top10_country_downloads` | JSON | Downloads by Region Page | Extracted from Country table with headers "Country", "Total downloads", "Share". Requires "yesterday" date filter. JSON structure: `[{"country": "US", "downloads": 12345, "share": "50.00%", "rank": 1}, ...]` |
| `top10_region_downloads` | JSON | Downloads by Region Page | Extracted from Region table with headers "Region", "Total downloads", "Share". Requires "yesterday" date filter. JSON structure: `[{"region": "NA", "downloads": 12345, "share": "50.00%", "rank": 1}, ...]` |
| `top10_country_revenue` | JSON | Regions and Countries Revenue Page | Extracted from Countries table. Requires "yesterday" date filter. JSON structure: `[{"country": "US", "revenue": 12345.67, "share": "50.00%", "rank": 1, "units": 1234, "change_vs_prior": "+5.23%", "arpu": 10.00}, ...]`. ARPU is enriched using players from `top10_country_dau` if available |
| `top10_region_revenue` | JSON | Regions and Countries Revenue Page | Extracted from Regions table. Requires "yesterday" date filter. JSON structure: `[{"region": "NA", "revenue": 12345.67, "share": "50.00%", "rank": 1, "units": 1234, "change_vs_prior": "+5.23%"}, ...]` |
| `iap_breakdown_json` | JSON | In-Game Purchases Page | Extracted from "Item Breakdown" table. Requires "yesterday" date filter. JSON structure: `[{"item": "Starter Pack", "id": "sku123", "units": 1000, "average_price": 1.99, "revenue": 1990.00, "rank": 1}, ...]`. Sorted by revenue descending |

---

## Page Extraction Order

1. **Default Game Page** (`extract_default_page_data`)
   - Fields: `unique_player`, `wishlist`, `lifetime_total_units`, `lifetime_total_revenue`, `median_playtime`
   - URL: `https://partner.steampowered.com/app/details/{app_id}/`
   - Date Filter: None (lifetime metrics)

2. **Lifetime Play Time Page** (`extract_playtime_page_data`)
   - Fields: `median_playtime` (fallback), `avg_playtime`, `players_20h_plus`
   - URL: `https://partner.steampowered.com//app/playtime/{app_id}/`
   - Date Filter: None (lifetime metrics)

3. **Wishlist Page** (`extract_wishlist_page_data`)
   - Fields: `wishlist_additions`, `wishlist_deletions`, `wishlist_conversions`, `lifetime_wishlist_conversion_rate`
   - URL: `https://partner.steampowered.com/app/wishlist/{app_id}/`
   - Date Filter: **Required** - "yesterday" button/link

4. **Players Page** (`extract_players_page_data`)
   - Fields: `dau`, `pcu`, `top10_country_dau`
   - URL: `https://partner.steampowered.com/app/players/{app_id}/`
   - Date Filter: **Required** - "yesterday" button/link

5. **Regions and Countries Revenue Page** (`extract_regions_revenue_page_data`)
   - Fields: `daily_total_revenue`, `daily_units`, `top10_region_revenue`, `top10_country_revenue`
   - URL: `https://partner.steampowered.com/region/?&appID={app_id}`
   - Date Filter: **Required** - "yesterday" button/link

6. **Downloads by Region Page** (`extract_downloads_region_page_data`)
   - Fields: `total_downloads`, `top10_region_downloads`, `top10_country_downloads`
   - URL: `https://partner.steampowered.com/nav_regions.php?downloads=1&appID={app_id}`
   - Date Filter: **Required** - "yesterday" button/link

7. **In-Game Purchases Page** (`extract_in_game_purchases_page_data`)
   - Fields: `iap_breakdown_json`, `top3_iap_share`
   - URL: `https://partner.steampowered.com/app/microtxn/{app_id}/`
   - Date Filter: **Required** - "yesterday" button/link

---

## Date Filter Mechanism

The crawler uses `set_yesterday_filter()` method which:
- Searches for "yesterday" buttons/links using multiple XPath selectors
- Clicks the first visible/enabled element found
- **Does NOT use dropdown date picker** - only looks for "yesterday" text elements
- This is why the remedy script's custom date approach fails on these pages

---

## Critical Dependencies

1. **`unique_player`** is the only critical field - if extraction fails, `extract_default_page_data()` returns `None`
2. **`new_players`** depends on `unique_player` from both today and yesterday
3. **`d1_retention`** depends on `dau` (today), `new_players`, and `dau` (yesterday from DB)
4. **`daily_arpu`** depends on `daily_total_revenue` and `dau`
5. **`top10_country_revenue`** ARPU enrichment depends on `top10_country_dau` being available
6. **`top3_iap_share`** depends on successful IAP breakdown extraction

---

## Notes

- All date-filtered pages require the "yesterday" filter to be set before extraction
- JSON fields are stored as JSON strings in the database
- Calculated fields return `NULL` if any required input is `NULL` or invalid
- The crawler processes pages sequentially and merges all extracted data before saving
