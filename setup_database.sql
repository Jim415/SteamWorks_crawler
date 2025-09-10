-- README: SteamWorks Crawler Database Schema
-- Purpose: Complete database setup for SteamWorks crawler with multi-table architecture
-- Scope: Main table for overview + individual game tables for performance optimization
-- 
-- ARCHITECTURE OVERVIEW:
--   - game_daily_metrics: Main table storing all games (primary key: steam_app_id + stat_date)
--   - delta_force_daily_metrics: Game-specific table for Delta Force (2507950)
--   - terminull_brigade_daily_metrics: Game-specific table for Terminull Brigade (3104410)  
--   - road_to_empress_daily_metrics: Game-specific table for Road to Empress (3478050)
--
-- COLUMN ORDER (Custom order for better readability):
--   stat_date, game_name, steam_app_id, dau, pcu, unique_player, new_players, 
--   total_downloads, d1_retention, pcu_over_dau, new_vs_returning_ratio, 
--   median_playtime, avg_playtime, players_20h_plus, lifetime_total_revenue, 
--   daily_total_revenue, lifetime_total_units, daily_units, daily_arpu, 
--   top3_iap_share, wishlist, lifetime_wishlist_conversion_rate, 
--   wishlist_additions, wishlist_deletions, wishlist_conversions, 
--   top10_country_dau, top10_country_downloads, top10_region_downloads, 
--   top10_country_revenue, top10_region_revenue, iap_breakdown_json
--
-- TIMEZONE/DATE RULE:
--   stat_date is computed as the Pacific Time date of the day that just ended when the crawler runs.
--   Example: crawler at 15:30 Beijing (~00:30 PT) on 2025-01-10 → stat_date = 2025-01-09.
--
-- JSON SHAPES (examples; ETL must ensure valid JSON arrays/objects):
--   top10_country_dau:       [{"country":"US","players":12345,"share":"50.00%","rank":1}, ...]
--   top10_country_downloads: [{"country":"US","downloads":12345,"share":"50.00%","rank":1}, ...]
--   top10_region_downloads:  [{"region":"NA","downloads":12345,"share":"50.00%","rank":1}, ...]
--   top10_country_revenue:   [{"country":"US","revenue":12345.67,"share":"50.00%","rank":1,"units":1234,"arpu":10.00}, ...]
--   top10_region_revenue:    [{"region":"NA","revenue":12345.67,"share":"50.00%","rank":1,"units":1234}, ...]
--   iap_breakdown_json:      [{"item":"Starter Pack","id":"sku123","units":1000,"average_price":1.99,"revenue":1990.00,"rank":1}, ...]

-- Create database with charset/collation
CREATE DATABASE IF NOT EXISTS steamworks_crawler
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE steamworks_crawler;

-- Create centralized daily metrics table (main table for all games)
CREATE TABLE IF NOT EXISTS game_daily_metrics (
    stat_date DATE NOT NULL,
    game_name VARCHAR(255) NULL,
    steam_app_id INT UNSIGNED NOT NULL,
    dau INT UNSIGNED NULL,
    pcu INT UNSIGNED NULL,
    unique_player INT UNSIGNED NULL,
    new_players INT UNSIGNED NULL,
    total_downloads INT UNSIGNED NULL,
    d1_retention DECIMAL(8,4) NULL,
    pcu_over_dau DECIMAL(8,4) NULL,
    new_vs_returning_ratio DECIMAL(8,4) NULL,
    median_playtime VARCHAR(255) NULL,
    avg_playtime VARCHAR(255) NULL,
    players_20h_plus INT UNSIGNED NULL,
    lifetime_total_revenue DECIMAL(14,2) NULL,
    daily_total_revenue DECIMAL(14,2) NULL,
    lifetime_total_units INT NULL,
    daily_units INT NULL,
    daily_arpu DECIMAL(12,6) NULL,
    top3_iap_share DECIMAL(8,4) NULL,
    wishlist INT UNSIGNED NULL,
    lifetime_wishlist_conversion_rate DECIMAL(8,4) NULL,
    wishlist_additions INT UNSIGNED NULL,
    wishlist_deletions INT UNSIGNED NULL,
    wishlist_conversions INT UNSIGNED NULL,
    top10_country_dau JSON NULL,
    top10_country_downloads JSON NULL,
    top10_region_downloads JSON NULL,
    top10_country_revenue JSON NULL,
    top10_region_revenue JSON NULL,
    iap_breakdown_json JSON NULL,

    PRIMARY KEY (steam_app_id, stat_date)
);

-- Create Delta Force specific table (steam_app_id: 2507950)
CREATE TABLE IF NOT EXISTS delta_force_daily_metrics (
    stat_date DATE NOT NULL PRIMARY KEY,
    game_name VARCHAR(255) NULL,
    steam_app_id INT UNSIGNED NOT NULL,
    dau INT UNSIGNED NULL,
    pcu INT UNSIGNED NULL,
    unique_player INT UNSIGNED NULL,
    new_players INT UNSIGNED NULL,
    total_downloads INT UNSIGNED NULL,
    d1_retention DECIMAL(8,4) NULL,
    pcu_over_dau DECIMAL(8,4) NULL,
    new_vs_returning_ratio DECIMAL(8,4) NULL,
    median_playtime VARCHAR(255) NULL,
    avg_playtime VARCHAR(255) NULL,
    players_20h_plus INT UNSIGNED NULL,
    lifetime_total_revenue DECIMAL(14,2) NULL,
    daily_total_revenue DECIMAL(14,2) NULL,
    lifetime_total_units INT NULL,
    daily_units INT NULL,
    daily_arpu DECIMAL(12,6) NULL,
    top3_iap_share DECIMAL(8,4) NULL,
    wishlist INT UNSIGNED NULL,
    lifetime_wishlist_conversion_rate DECIMAL(8,4) NULL,
    wishlist_additions INT UNSIGNED NULL,
    wishlist_deletions INT UNSIGNED NULL,
    wishlist_conversions INT UNSIGNED NULL,
    top10_country_dau JSON NULL,
    top10_country_downloads JSON NULL,
    top10_region_downloads JSON NULL,
    top10_country_revenue JSON NULL,
    top10_region_revenue JSON NULL,
    iap_breakdown_json JSON NULL
);

-- Create Terminull Brigade specific table (steam_app_id: 3104410)
CREATE TABLE IF NOT EXISTS terminull_brigade_daily_metrics (
    stat_date DATE NOT NULL PRIMARY KEY,
    game_name VARCHAR(255) NULL,
    steam_app_id INT UNSIGNED NOT NULL,
    dau INT UNSIGNED NULL,
    pcu INT UNSIGNED NULL,
    unique_player INT UNSIGNED NULL,
    new_players INT UNSIGNED NULL,
    total_downloads INT UNSIGNED NULL,
    d1_retention DECIMAL(8,4) NULL,
    pcu_over_dau DECIMAL(8,4) NULL,
    new_vs_returning_ratio DECIMAL(8,4) NULL,
    median_playtime VARCHAR(255) NULL,
    avg_playtime VARCHAR(255) NULL,
    players_20h_plus INT UNSIGNED NULL,
    lifetime_total_revenue DECIMAL(14,2) NULL,
    daily_total_revenue DECIMAL(14,2) NULL,
    lifetime_total_units INT NULL,
    daily_units INT NULL,
    daily_arpu DECIMAL(12,6) NULL,
    top3_iap_share DECIMAL(8,4) NULL,
    wishlist INT UNSIGNED NULL,
    lifetime_wishlist_conversion_rate DECIMAL(8,4) NULL,
    wishlist_additions INT UNSIGNED NULL,
    wishlist_deletions INT UNSIGNED NULL,
    wishlist_conversions INT UNSIGNED NULL,
    top10_country_dau JSON NULL,
    top10_country_downloads JSON NULL,
    top10_region_downloads JSON NULL,
    top10_country_revenue JSON NULL,
    top10_region_revenue JSON NULL,
    iap_breakdown_json JSON NULL
);

-- Create Road to Empress specific table (steam_app_id: 3478050)
CREATE TABLE IF NOT EXISTS road_to_empress_daily_metrics (
    stat_date DATE NOT NULL PRIMARY KEY,
    game_name VARCHAR(255) NULL,
    steam_app_id INT UNSIGNED NOT NULL,
    dau INT UNSIGNED NULL,
    pcu INT UNSIGNED NULL,
    unique_player INT UNSIGNED NULL,
    new_players INT UNSIGNED NULL,
    total_downloads INT UNSIGNED NULL,
    d1_retention DECIMAL(8,4) NULL,
    pcu_over_dau DECIMAL(8,4) NULL,
    new_vs_returning_ratio DECIMAL(8,4) NULL,
    median_playtime VARCHAR(255) NULL,
    avg_playtime VARCHAR(255) NULL,
    players_20h_plus INT UNSIGNED NULL,
    lifetime_total_revenue DECIMAL(14,2) NULL,
    daily_total_revenue DECIMAL(14,2) NULL,
    lifetime_total_units INT NULL,
    daily_units INT NULL,
    daily_arpu DECIMAL(12,6) NULL,
    top3_iap_share DECIMAL(8,4) NULL,
    wishlist INT UNSIGNED NULL,
    lifetime_wishlist_conversion_rate DECIMAL(8,4) NULL,
    wishlist_additions INT UNSIGNED NULL,
    wishlist_deletions INT UNSIGNED NULL,
    wishlist_conversions INT UNSIGNED NULL,
    top10_country_dau JSON NULL,
    top10_country_downloads JSON NULL,
    top10_region_downloads JSON NULL,
    top10_country_revenue JSON NULL,
    top10_region_revenue JSON NULL,
    iap_breakdown_json JSON NULL
);

-- Verify table creation
SELECT 'Database setup completed successfully!' as status;
SELECT TABLE_NAME, TABLE_ROWS 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'steamworks_crawler' 
AND TABLE_NAME LIKE '%_daily_metrics'
ORDER BY TABLE_NAME;