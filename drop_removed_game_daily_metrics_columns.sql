USE steamworks_crawler;

SET @sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'game_daily_metrics'
              AND COLUMN_NAME = 'd1_retention'
        ),
        'ALTER TABLE game_daily_metrics DROP COLUMN d1_retention',
        'SELECT ''Column d1_retention does not exist - skipped.'' AS status'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'game_daily_metrics'
              AND COLUMN_NAME = 'pcu_over_dau'
        ),
        'ALTER TABLE game_daily_metrics DROP COLUMN pcu_over_dau',
        'SELECT ''Column pcu_over_dau does not exist - skipped.'' AS status'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'game_daily_metrics'
              AND COLUMN_NAME = 'players_20h_plus'
        ),
        'ALTER TABLE game_daily_metrics DROP COLUMN players_20h_plus',
        'SELECT ''Column players_20h_plus does not exist - skipped.'' AS status'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'game_daily_metrics'
              AND COLUMN_NAME = 'new_vs_returning_ratio'
        ),
        'ALTER TABLE game_daily_metrics DROP COLUMN new_vs_returning_ratio',
        'SELECT ''Column new_vs_returning_ratio does not exist - skipped.'' AS status'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'game_daily_metrics'
              AND COLUMN_NAME = 'avg_playtime'
        ),
        'ALTER TABLE game_daily_metrics DROP COLUMN avg_playtime',
        'SELECT ''Column avg_playtime does not exist - skipped.'' AS status'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'game_daily_metrics'
              AND COLUMN_NAME = 'top3_iap_share'
        ),
        'ALTER TABLE game_daily_metrics DROP COLUMN top3_iap_share',
        'SELECT ''Column top3_iap_share does not exist - skipped.'' AS status'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'game_daily_metrics'
              AND COLUMN_NAME = 'iap_breakdown_json'
        ),
        'ALTER TABLE game_daily_metrics DROP COLUMN iap_breakdown_json',
        'SELECT ''Column iap_breakdown_json does not exist - skipped.'' AS status'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
