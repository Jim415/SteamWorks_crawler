# Newcomer Guide: SteamWorks Crawler

## What this repository does

This project automates SteamWorks data collection for multiple games, stores daily metrics in MySQL, and provides monitoring + visualization workflows.

At a high level there are three pipelines:

1. **Core crawler** (`steamworks_crawler.py`) for gameplay/revenue/wishlist/player metrics.
2. **Marketing crawler** (`steamworks_marketing_crawler.py`) for Store Traffic Stats and feature-level traffic breakdowns.
3. **Monitoring and analytics** (`crawler_alert_monitor.py`, `Visualization/`) for operational health checks and dashboarding.

## Top-level structure

- `steamworks_crawler.py`  
  Main production crawler. Uses Selenium to login to SteamWorks, navigate multiple pages, extract values, and write one row per game/date.

- `steamworks_marketing_crawler.py`  
  Extracts marketing/store traffic data, including bilingual (Chinese/English) feature normalization.

- `steamworks_historical_marketing_crawler.py` + `run_historical_crawler.py`  
  Historical backfill workflow for marketing data over date ranges.

- `crawler_alert_monitor.py` + `ALERT_MONITOR_README.md`  
  Post-run checks for missing/incorrect/incomplete records and alerting.

- `setup_database.sql` and `setup_marketing_database.sql`  
  Schema setup for core and marketing tables.

- `Visualization/`  
  Notebook + scripts for dashboard generation, exports, and email alerts.

- `tests/` + `html file example/`  
  Debugging scripts and sample HTML snapshots used to verify parsing behavior.

## Important architecture concepts

### 1) Date semantics and timezone

The crawlers treat `stat_date` as the **Pacific day that just ended** (typically “yesterday” in PT when run in Asia timezone operations). This is a critical rule for interpreting data correctness checks and alert logic.

### 2) Source-of-truth storage model

Core metrics are stored in `game_daily_metrics` keyed by `(steam_app_id, stat_date)`, which makes each app/date idempotent and dedupe-friendly.

### 3) Browser profile strategy

The crawler supports both local persistent profiles and cloning system Chrome profiles via environment variables. This is what reduces repeated Steam Guard prompts and stabilizes authentication.

### 4) Resilience patterns

Scripts use retries, re-navigation, and guarded extraction so partial scrape failures do not necessarily abort the whole run.

### 5) Bilingual feature normalization

Marketing extraction uses a Chinese→English feature mapping dictionary and pattern matching helpers to keep downstream metrics consistent.

## What to learn first (recommended order)

1. Read `README.md` end-to-end for the product-level workflow.
2. Skim `STEAMWORKS_CRAWLER_DOCUMENTATION.md` to understand each field’s source page and destination column.
3. Trace `SteamWorksCrawler.run()` flow in `steamworks_crawler.py` (setup driver → auth → page extraction → DB write).
4. Read `steamworks_marketing_crawler.py` extraction helpers, especially feature-name translation and homepage parsing.
5. Review `crawler_alert_monitor.py` to understand operational SLAs and failure detection.
6. Open `Visualization/README.md` and run the dashboard pipeline locally.

## Practical onboarding tips

- Start with one game/app ID in a dev DB before scaling to all configured games.
- Keep credentials out of code; move to env vars or local config files.
- Use sample HTML files in `html file example/` to debug selectors without repeatedly hitting SteamWorks.
- When changing selectors, run both core and marketing checks because DOM changes often affect multiple scripts.
- Validate outputs at two levels: raw extracted values in logs + final rows in MySQL.

## Where to contribute next

- Replace hardcoded DB credentials with environment-driven configuration across all scripts.
- Consolidate duplicated Selenium utility logic shared by core + marketing crawlers.
- Add regression tests that parse saved HTML fixtures for key fields.
- Add schema/version migration tooling for reproducible deployments.
- Add CI lint/test jobs for parser safety before production runs.
