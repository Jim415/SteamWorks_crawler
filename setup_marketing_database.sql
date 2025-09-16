-- Marketing Crawler Database Schema
-- This file creates the database tables for Steamworks Marketing Crawler

-- Overall table for all games
CREATE TABLE IF NOT EXISTS game_daily_marketing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    steam_app_id INT NOT NULL,
    game_name VARCHAR(100) NOT NULL,
    stat_date DATE NOT NULL,
    
    -- Main metrics
    total_impressions BIGINT DEFAULT 0,
    total_visits BIGINT DEFAULT 0,
    total_click_through_rate DECIMAL(5,2) DEFAULT 0,
    owner_visits BIGINT DEFAULT 0,
    
    -- JSON data fields
    top_country_visits JSON,
    takeover_banner JSON,
    pop_up_message JSON,
    main_cluster JSON,
    all_source_breakdown JSON,
    homepage_breakdown JSON,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE KEY unique_daily_marketing (steam_app_id, stat_date),
    INDEX idx_steam_app_id (steam_app_id),
    INDEX idx_stat_date (stat_date),
    INDEX idx_game_name (game_name)
);

-- Individual game tables (same structure, different names)
CREATE TABLE IF NOT EXISTS delta_force_daily_marketing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    steam_app_id INT NOT NULL,
    game_name VARCHAR(100) NOT NULL,
    stat_date DATE NOT NULL,
    
    -- Main metrics
    total_impressions BIGINT DEFAULT 0,
    total_visits BIGINT DEFAULT 0,
    total_click_through_rate DECIMAL(5,2) DEFAULT 0,
    owner_visits BIGINT DEFAULT 0,
    
    -- JSON data fields
    top_country_visits JSON,
    takeover_banner JSON,
    pop_up_message JSON,
    main_cluster JSON,
    all_source_breakdown JSON,
    homepage_breakdown JSON,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE KEY unique_delta_force_daily (steam_app_id, stat_date),
    INDEX idx_stat_date (stat_date)
);

CREATE TABLE IF NOT EXISTS terminull_brigade_daily_marketing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    steam_app_id INT NOT NULL,
    game_name VARCHAR(100) NOT NULL,
    stat_date DATE NOT NULL,
    
    -- Main metrics
    total_impressions BIGINT DEFAULT 0,
    total_visits BIGINT DEFAULT 0,
    total_click_through_rate DECIMAL(5,2) DEFAULT 0,
    owner_visits BIGINT DEFAULT 0,
    
    -- JSON data fields
    top_country_visits JSON,
    takeover_banner JSON,
    pop_up_message JSON,
    main_cluster JSON,
    all_source_breakdown JSON,
    homepage_breakdown JSON,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE KEY unique_terminull_brigade_daily (steam_app_id, stat_date),
    INDEX idx_stat_date (stat_date)
);

CREATE TABLE IF NOT EXISTS road_to_empress_daily_marketing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    steam_app_id INT NOT NULL,
    game_name VARCHAR(100) NOT NULL,
    stat_date DATE NOT NULL,
    
    -- Main metrics
    total_impressions BIGINT DEFAULT 0,
    total_visits BIGINT DEFAULT 0,
    total_click_through_rate DECIMAL(5,2) DEFAULT 0,
    owner_visits BIGINT DEFAULT 0,
    
    -- JSON data fields
    top_country_visits JSON,
    takeover_banner JSON,
    pop_up_message JSON,
    main_cluster JSON,
    all_source_breakdown JSON,
    homepage_breakdown JSON,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE KEY unique_road_to_empress_daily (steam_app_id, stat_date),
    INDEX idx_stat_date (stat_date)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_game_daily_marketing_composite ON game_daily_marketing (steam_app_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_delta_force_composite ON delta_force_daily_marketing (steam_app_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_terminull_brigade_composite ON terminull_brigade_daily_marketing (steam_app_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_road_to_empress_composite ON road_to_empress_daily_marketing (steam_app_id, stat_date);

-- Insert sample data structure comments
-- Example JSON structures for reference:

-- top_country_visits: [{"country": "United States", "visits": 12345, "percentage": 25.5}, ...]
-- takeover_banner: {"impressions": 1000000, "visits": 50000, "click_thru_rate": 5.0}
-- pop_up_message: {"impressions": 500000, "visits": 25000, "click_thru_rate": 5.0}
-- main_cluster: {"recommended_for_you": {...}, "top_seller": {...}, "friend_recommendation": {...}}
-- all_source_breakdown: {"home_page": {...}, "search_suggestions": {...}, "direct_navigation": {...}}
-- homepage_breakdown: {"takeover_banner": {...}, "new_and_trending": {...}, "marketing_message": {...}}

-- Show table creation confirmation
SELECT 'Marketing database tables created successfully' AS status;
