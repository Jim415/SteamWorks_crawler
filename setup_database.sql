-- README: steamworks_crawler.game_daily_metrics
-- Purpose: Centralized daily metrics table. One row per Steam app per Pacific date (stat_date = PT_today - 1 when crawler runs after midnight PT).
-- Scope: Storage only; ETL/crawler performs all calculations; revenue in USD; JSON values are pre-shaped by ETL.
-- Column dictionary
--   Identifiers & metadata
--     steam_app_id INT UNSIGNED NOT NULL
--     game_name VARCHAR(255) NULL
--     stat_date DATE NOT NULL  -- Pacific date that just closed
--     notes VARCHAR(255) NULL
--   Core activity
--     dau INT UNSIGNED NULL
--     pcu INT UNSIGNED NULL
--     new_players INT UNSIGNED NULL
--     total_downloads INT UNSIGNED NULL
--     pcu_over_dau DECIMAL(8,4) NULL
--     players_20h_plus INT UNSIGNED NULL
--     unique_player INT UNSIGNED NULL
--   Playtime (seconds)
--     median_playtime VARCHAR(255) NULL
--     avg_playtime VARCHAR(255) NULL
--   Retention & mix (precomputed)
--     d1_retention DECIMAL(8,4) NULL
--     new_vs_returning_ratio DECIMAL(8,4) NULL
--   Revenue (USD)
--     daily_total_revenue DECIMAL(14,2) NULL
--     lifetime_total_revenue DECIMAL(14,2) NULL
--     daily_arpu DECIMAL(12,6) NULL
--     top3_iap_share DECIMAL(8,4) NULL
--   Wishlist
--     wishlist INT UNSIGNED NULL
--     wishlist_additions INT UNSIGNED NULL
--     wishlist_deletions INT UNSIGNED NULL
--     wishlist_conversions INT UNSIGNED NULL
--     lifetime_wishlist_conversion_rate DECIMAL(8,4) NULL
--   Geo & IAP (JSON arrays; shapes documented below)
--     top10_country_dau JSON NULL
--     top10_country_downloads JSON NULL
--     top10_region_downloads JSON NULL
--     top10_country_revenue JSON NULL
--     top10_region_revenue JSON NULL
--     iap_breakdown_json JSON NULL
-- Constraints
--   PRIMARY KEY (steam_app_id, stat_date)
-- Timezone/date rule
--   stat_date is computed as the Pacific Time date of the day that just ended when the crawler runs.
--   Example: crawler at 15:30 Beijing (~00:30 PT) on 2025-01-10 → stat_date = 2025-01-09.
-- JSON shapes (examples; ETL must ensure valid JSON arrays/objects)
--   top10_country_dau:       [{"country":"US","players":12345,"share":0.2345,"rank":1}, ...]
--   top10_country_downloads: [{"country":"US","downloads":12345,"share":0.2345,"rank":1}, ...]
--   top10_region_downloads:  [{"region":"NA","downloads":12345,"share":0.2345,"rank":1}, ...]
--   top10_country_revenue:   [{"country":"US","revenue":12345.67,"share":0.2345,"rank":1}, ...]
--   top10_region_revenue:    [{"region":"NA","revenue":12345.67,"share":0.2345,"rank":1}, ...]
--   iap_breakdown_json:      [{"item":"Starter Pack","id":"sku123","units":1000,"avg_price":1.99,"revenue":1990.00}, ...]

-- Create database with charset/collation
CREATE DATABASE IF NOT EXISTS steamworks_crawler
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE steamworks_crawler;

-- Create centralized daily metrics table
CREATE TABLE IF NOT EXISTS game_daily_metrics (
    steam_app_id INT UNSIGNED NOT NULL,
    game_name VARCHAR(255) NULL,
    stat_date DATE NOT NULL,
    notes VARCHAR(255) NULL,

    -- Core activity
    dau INT UNSIGNED NULL,
    pcu INT UNSIGNED NULL,
    new_players INT UNSIGNED NULL,
    total_downloads INT UNSIGNED NULL,
    pcu_over_dau DECIMAL(8,4) NULL,
    players_20h_plus INT UNSIGNED NULL,
    unique_player INT UNSIGNED NULL,

    -- Playtime (seconds) as provided by ETL (string if bucketed)
    median_playtime VARCHAR(255) NULL,
    avg_playtime VARCHAR(255) NULL,

    -- Retention & mix (precomputed)
    d1_retention DECIMAL(8,4) NULL,
    new_vs_returning_ratio DECIMAL(8,4) NULL,

    -- Revenue (USD)
    daily_total_revenue DECIMAL(14,2) NULL,
    lifetime_total_revenue DECIMAL(14,2) NULL,
    daily_arpu DECIMAL(12,6) NULL,
    top3_iap_share DECIMAL(8,4) NULL,

    -- Wishlist
    wishlist INT UNSIGNED NULL,
    wishlist_additions INT UNSIGNED NULL,
    wishlist_deletions INT UNSIGNED NULL,
    wishlist_conversions INT UNSIGNED NULL,
    lifetime_wishlist_conversion_rate DECIMAL(8,4) NULL,

    -- Geo & IAP (JSON arrays)
    top10_country_dau JSON NULL,
    top10_country_downloads JSON NULL,
    top10_region_downloads JSON NULL,
    top10_country_revenue JSON NULL,
    top10_region_revenue JSON NULL,
    iap_breakdown_json JSON NULL,

    PRIMARY KEY (steam_app_id, stat_date)
);