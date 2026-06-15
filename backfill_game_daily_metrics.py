#!/usr/bin/env python3
"""
Backfill missing game_daily_metrics rows for a historical date range.

This script intentionally reuses SteamWorksCrawler extraction logic and only
changes the date-selection and database-write behavior:
- date selection is done by adding dateStart/dateEnd query parameters
- only historical-safe fields are inserted2
- existing rows are never overwritten
"""

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import mysql.connector
from mysql.connector import Error

from db_config import get_db_config
from steamworks_crawler import SteamWorksCrawler

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("backfill_game_daily_metrics.log"),
        logging.StreamHandler(),
    ],
)


GAMES = [
    (2507950, "Delta Force"),
    (2073620, "Arena Breakout: Infinite"),
    (3478050, "Road to Empress"),
    (3104410, "Terminull Brigade"),
]


def parse_date_input(date_str):
    """Parse YYYYMMDD into a date."""
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYYMMDD.")


def pacific_yesterday():
    if ZoneInfo:
        now_pt = datetime.now(ZoneInfo("America/Los_Angeles"))
        return (now_pt - timedelta(days=1)).date()
    return (datetime.now() - timedelta(days=1)).date()


def iter_date_range(start_date, end_date):
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def dated_url(url, target_date):
    """Return URL with a single-day date range and immediate prior day."""
    prior_date = target_date - timedelta(days=1)
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params.pop("specialPeriod", None)
    params.update(
        {
            "dateStart": target_date.isoformat(),
            "dateEnd": target_date.isoformat(),
            "priorDateStart": prior_date.isoformat(),
            "priorDateEnd": prior_date.isoformat(),
        }
    )
    return urlunparse(parsed._replace(query=urlencode(params)))


def check_existing_rows(db_config, target_date):
    """Return existing game_daily_metrics rows for the target date."""
    app_ids = [app_id for app_id, _ in GAMES]
    placeholders = ", ".join(["%s"] * len(app_ids))
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT steam_app_id, game_name, stat_date
            FROM game_daily_metrics
            WHERE stat_date = %s
              AND steam_app_id IN ({placeholders})
            ORDER BY steam_app_id
            """.format(placeholders=placeholders),
            (target_date, *app_ids),
        )
        return cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_previous_day_values(db_config, steam_app_id, target_date):
    """Load prior-day values needed for backfilled derived/carry-forward fields."""
    previous_date = target_date - timedelta(days=1)
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT median_playtime,
                   lifetime_total_revenue,
                   lifetime_total_units,
                   wishlist
            FROM game_daily_metrics
            WHERE steam_app_id = %s
              AND stat_date = %s
            """,
            (steam_app_id, previous_date),
        )
        return cursor.fetchone() or {}
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def build_backfill_plan(db_config, target_dates):
    """Return per-date existing and missing games without allowing overwrites."""
    plan = []
    games_by_app_id = {app_id: name for app_id, name in GAMES}

    for target_date in target_dates:
        existing_rows = check_existing_rows(db_config, target_date)
        existing_app_ids = {int(row["steam_app_id"]) for row in existing_rows}
        existing_games = [
            (app_id, games_by_app_id[app_id])
            for app_id in existing_app_ids
            if app_id in games_by_app_id
        ]
        missing_games = [
            (app_id, name)
            for app_id, name in GAMES
            if app_id not in existing_app_ids
        ]
        plan.append(
            {
                "target_date": target_date,
                "existing_games": sorted(existing_games),
                "missing_games": missing_games,
            }
        )

    return plan


class SteamWorksDailyMetricsBackfillCrawler(SteamWorksCrawler):
    def __init__(self, db_config, steam_app_id, game_name, target_date):
        super().__init__(db_config, steam_app_id, game_name)
        self.target_date = target_date

    def set_yesterday_filter(self):
        """
        Existing extraction methods call set_yesterday_filter().
        For backfill, redirect the current page to the single target date.
        """
        try:
            current_url = self.driver.current_url
            target_url = dated_url(current_url, self.target_date)
            logging.info(f"Setting historical date filter via URL: {target_url}")
            self.driver.get(target_url)
            time.sleep(3)
            return self.verify_target_date_selected()
        except Exception as exc:
            logging.warning(f"Error setting historical date filter: {exc}")
            return False

    def verify_target_date_selected(self):
        page_source = self.driver.page_source or ""
        target = self.target_date.isoformat()
        checks = [
            f'name="dateStart" SIZE=9 VALUE="{target}"',
            f"dateStart={target}",
            f"dateStart&quot;:&quot;{target}&quot;",
            f"{target} to {target}",
        ]
        if any(check in page_source for check in checks):
            logging.info(f"Verified page is filtered to {target}")
            return True
        logging.warning(f"Could not verify page date filter for {target}")
        return False

    def save_backfill_to_database(self, data):
        """Insert historical-safe fields into game_daily_metrics only."""
        if not data:
            logging.warning("No data to save")
            return False

        previous_values = get_previous_day_values(self.db_config, self.steam_app_id, self.target_date)

        daily_arpu_val = None
        try:
            revenue_val = data.get("daily_total_revenue")
            dau_val = data.get("dau")
            if revenue_val is not None and dau_val is not None and float(dau_val) > 0:
                daily_arpu_val = round(float(revenue_val) / float(dau_val), 2)
        except Exception:
            daily_arpu_val = None

        lifetime_total_revenue_val = None
        try:
            previous_revenue = previous_values.get("lifetime_total_revenue")
            daily_revenue = data.get("daily_total_revenue")
            if previous_revenue is not None and daily_revenue is not None:
                lifetime_total_revenue_val = round(float(previous_revenue) + float(daily_revenue), 2)
        except Exception:
            lifetime_total_revenue_val = None

        lifetime_total_units_val = None
        try:
            previous_units = previous_values.get("lifetime_total_units")
            daily_units = data.get("daily_units")
            if previous_units is not None and daily_units is not None:
                lifetime_total_units_val = int(previous_units) + int(daily_units)
        except Exception:
            lifetime_total_units_val = None

        wishlist_val = None
        try:
            previous_wishlist = previous_values.get("wishlist")
            additions = data.get("wishlist_additions")
            deletions = data.get("wishlist_deletions")
            conversions = data.get("wishlist_conversions")
            if previous_wishlist is not None and additions is not None and deletions is not None and conversions is not None:
                wishlist_val = int(previous_wishlist) + int(additions) - int(deletions) - int(conversions)
                if wishlist_val < 0:
                    wishlist_val = 0
        except Exception:
            wishlist_val = None

        insert_payload = {
            "steam_app_id": int(self.steam_app_id),
            "game_name": self.game_name,
            "stat_date": self.target_date,
            "dau": data.get("dau"),
            "pcu": data.get("pcu"),
            "total_downloads": data.get("total_downloads"),
            "daily_total_revenue": data.get("daily_total_revenue"),
            "daily_units": data.get("daily_units"),
            "daily_arpu": daily_arpu_val,
            "lifetime_total_revenue": lifetime_total_revenue_val,
            "lifetime_total_units": lifetime_total_units_val,
            "wishlist": wishlist_val,
            "lifetime_wishlist_conversion_rate": data.get("lifetime_wishlist_conversion_rate"),
            "wishlist_additions": data.get("wishlist_additions"),
            "wishlist_deletions": data.get("wishlist_deletions"),
            "wishlist_conversions": data.get("wishlist_conversions"),
            "median_playtime": previous_values.get("median_playtime"),
            "top10_country_dau": json.dumps(data.get("top10_country_dau")) if data.get("top10_country_dau") is not None else None,
            "top10_country_downloads": json.dumps(data.get("top10_country_downloads")) if data.get("top10_country_downloads") is not None else None,
            "top10_region_downloads": json.dumps(data.get("top10_region_downloads")) if data.get("top10_region_downloads") is not None else None,
            "top10_country_revenue": json.dumps(data.get("top10_country_revenue")) if data.get("top10_country_revenue") is not None else None,
            "top10_region_revenue": json.dumps(data.get("top10_region_revenue")) if data.get("top10_region_revenue") is not None else None,
        }
        insert_payload = {key: value for key, value in insert_payload.items() if value is not None}

        columns = list(insert_payload.keys())
        placeholders = ", ".join([f"%({column})s" for column in columns])
        column_names = ", ".join(columns)
        query = f"INSERT INTO game_daily_metrics ({column_names}) VALUES ({placeholders})"

        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor()
            cursor.execute(query, insert_payload)
            connection.commit()
            logging.info(f"Inserted backfill row for {self.game_name} on {self.target_date}")
            return True
        except Error as exc:
            if connection:
                connection.rollback()
            logging.error(f"Database error while saving backfill: {exc}")
            return False
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    def run_backfill(self):
        start_time = time.time()
        try:
            logging.info(f"Starting backfill for {self.game_name} ({self.steam_app_id}) on {self.target_date}")
            self.setup_driver()
            self.warmup_session()
            self.ensure_partner_context()

            all_data = {}

            logging.info("=== Extracting historical Players Page ===")
            players_data = self.extract_players_page_data()
            if players_data:
                all_data.update(players_data)

            logging.info("=== Extracting historical Wishlist Page ===")
            wishlist_data = self.extract_wishlist_page_data()
            if wishlist_data:
                all_data.update(wishlist_data)

            logging.info("=== Extracting historical Regions Revenue Page ===")
            revenue_data = self.extract_regions_revenue_page_data()
            if revenue_data:
                all_data.update(revenue_data)

            logging.info("=== Extracting historical Downloads Region Page ===")
            downloads_data = self.extract_downloads_region_page_data()
            if downloads_data:
                all_data.update(downloads_data)

            if not all_data:
                return False, "Data extraction failed"

            success = self.save_backfill_to_database(all_data)
            elapsed = time.time() - start_time
            if success:
                return True, f"Inserted {self.game_name} {self.target_date} in {elapsed:.2f}s"
            return False, "Database save failed"
        except Exception as exc:
            logging.error(f"Backfill failed for {self.game_name}: {exc}")
            return False, str(exc)
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver closed")


def main():
    print("=" * 80)
    print("SteamWorks game_daily_metrics Historical Backfill")
    print("=" * 80)
    print("This script inserts missing historical dates into game_daily_metrics.")
    print("It never overwrites existing rows.")
    print()

    start_input = input("Enter start date (YYYYMMDD): ").strip()
    if not start_input:
        print("[ERROR] No start date provided.")
        sys.exit(1)

    end_input = input("Enter end date (YYYYMMDD): ").strip()
    if not end_input:
        print("[ERROR] No end date provided.")
        sys.exit(1)

    try:
        start_date = parse_date_input(start_input)
        end_date = parse_date_input(end_input)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    if start_date > end_date:
        print("[ERROR] Start date must be earlier than or equal to end date.")
        sys.exit(1)

    latest_allowed_date = pacific_yesterday()
    if end_date > latest_allowed_date:
        print(f"[ERROR] Target date must be historical. Latest allowed date: {latest_allowed_date}")
        sys.exit(1)

    target_dates = list(iter_date_range(start_date, end_date))

    db_config = get_db_config()
    backfill_plan = build_backfill_plan(db_config, target_dates)
    total_missing_games = sum(len(item["missing_games"]) for item in backfill_plan)

    print("\nBackfill plan:")
    print(f"  Date range: {start_date} to {end_date} ({len(target_dates)} day(s))")
    print("  Table: game_daily_metrics")
    print(f"  Games needing backfill: {total_missing_games}")
    print("  Fields: historical-safe metrics, wishlist fields, and prior-day derived fields")

    for item in backfill_plan:
        target_date = item["target_date"]
        existing_games = item["existing_games"]
        missing_games = item["missing_games"]
        print(f"\n  Date: {target_date}")
        if existing_games:
            print("    Existing rows (skip, no overwrite):")
            for app_id, name in existing_games:
                print(f"      - {name} ({app_id})")
        if missing_games:
            print("    Missing rows (will backfill):")
            for app_id, name in missing_games:
                print(f"      - {name} ({app_id})")
        else:
            print("    No missing rows. This date will be skipped.")

    if total_missing_games == 0:
        print("\nNothing to backfill. All target rows already exist.")
        return

    confirm = input("\nProceed? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    overall_success = True
    for item in backfill_plan:
        target_date = item["target_date"]
        missing_games = item["missing_games"]
        if not missing_games:
            print(f"\nSkipping {target_date}: all target rows already exist.")
            continue

        print(f"\n{'=' * 80}")
        print(f"Backfilling date: {target_date}")
        print(f"{'=' * 80}")
        for app_id, name in missing_games:
            print(f"\n=== Backfilling {name} ({app_id}) for {target_date} ===")
            crawler = SteamWorksDailyMetricsBackfillCrawler(db_config, app_id, name, target_date)
            success, result = crawler.run_backfill()
            if success:
                print(f"Success: {result}")
            else:
                print(f"Failed: {result}")
                overall_success = False

    if overall_success:
        print("\nAll backfills completed.")
    else:
        print("\nSome backfills failed. See logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
