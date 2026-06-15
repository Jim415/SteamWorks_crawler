#!/usr/bin/env python3
"""
Repair historical revenue geography JSON fields in game_daily_metrics.

This script reuses SteamWorksCrawler.extract_regions_revenue_page_data() and only
updates:
- top10_country_revenue
- top10_region_revenue
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


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("repair_revenue_geography_json.log"),
        logging.StreamHandler(),
    ],
)


def parse_date_input(date_str):
    """Parse YYYYMMDD into a date."""
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYYMMDD.")


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


def load_existing_rows(db_config, start_date, end_date):
    """Load existing rows in the target range. Missing rows are not created."""
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT steam_app_id, game_name, stat_date
            FROM game_daily_metrics
            WHERE stat_date BETWEEN %s AND %s
            ORDER BY stat_date, steam_app_id
            """,
            (start_date, end_date),
        )
        return cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def summarize_rows(rows):
    """Return row counts grouped by app id and game name for preview output."""
    summary = {}
    for row in rows:
        key = (int(row["steam_app_id"]), row["game_name"])
        summary[key] = summary.get(key, 0) + 1
    return summary


def update_revenue_json(db_config, row, revenue_data):
    """Update only the two revenue geography JSON columns for one existing row."""
    country_revenue = revenue_data.get("top10_country_revenue")
    region_revenue = revenue_data.get("top10_region_revenue")
    if not isinstance(country_revenue, list) or not isinstance(region_revenue, list):
        raise ValueError("Revenue geography extraction did not return both JSON lists.")

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE game_daily_metrics
            SET top10_country_revenue = %s,
                top10_region_revenue = %s
            WHERE steam_app_id = %s
              AND stat_date = %s
            """,
            (
                json.dumps(country_revenue),
                json.dumps(region_revenue),
                int(row["steam_app_id"]),
                row["stat_date"],
            ),
        )
        connection.commit()
        return cursor.rowcount
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


class SteamWorksRevenueGeographyRepairCrawler(SteamWorksCrawler):
    def __init__(self, db_config, steam_app_id, game_name, target_date):
        super().__init__(db_config, steam_app_id, game_name)
        self.target_date = target_date

    def set_yesterday_filter(self):
        """
        Existing extraction calls set_yesterday_filter().
        For repair, redirect the current page to the historical target date.
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

    def run_repair_extract(self):
        try:
            self.setup_driver()
            self.warmup_session()
            self.ensure_partner_context()
            return self.extract_regions_revenue_page_data()
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver closed")


def repair_row(db_config, row):
    crawler = SteamWorksRevenueGeographyRepairCrawler(
        db_config=db_config,
        steam_app_id=int(row["steam_app_id"]),
        game_name=row["game_name"],
        target_date=row["stat_date"],
    )
    revenue_data = crawler.run_repair_extract()
    if not revenue_data:
        return False, "Revenue geography extraction failed"
    updated_count = update_revenue_json(db_config, row, revenue_data)
    return True, f"Updated {updated_count} row(s)"


def main():
    print("=" * 80)
    print("SteamWorks Historical Revenue Geography JSON Repair")
    print("=" * 80)
    print("Table: game_daily_metrics")
    print("Columns to update: top10_country_revenue, top10_region_revenue")
    print("Rows are updated only when they already exist.")
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

    db_config = get_db_config()
    rows = load_existing_rows(db_config, start_date, end_date)
    if not rows:
        print("[ERROR] No existing rows found in the target date range.")
        sys.exit(1)

    summary = summarize_rows(rows)
    print(f"Date range: {start_date} to {end_date}")
    print(f"Rows to process: {len(rows)}")
    print("Rows by game:")
    for (steam_app_id, game_name), count in sorted(summary.items()):
        print(f"  - {game_name} ({steam_app_id}): {count}")
    print()
    print("This will crawl one historical Regions and Countries revenue page per row.")
    print("Type YES to update the live database. Anything else will abort.")
    confirmation = input("Confirm repair: ").strip()
    if confirmation != "YES":
        print("Aborted. No database changes were made.")
        return

    updated = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    for index, row in enumerate(rows, start=1):
        label = f"{row['stat_date']} | {row['game_name']} ({row['steam_app_id']})"
        logging.info(f"[{index}/{len(rows)}] Repairing {label}")
        try:
            success, message = repair_row(db_config, row)
            if success:
                updated += 1
                logging.info(f"[{index}/{len(rows)}] SUCCESS {label}: {message}")
            else:
                skipped += 1
                logging.warning(f"[{index}/{len(rows)}] SKIPPED {label}: {message}")
        except (Error, Exception) as exc:
            failed += 1
            logging.error(f"[{index}/{len(rows)}] FAILED {label}: {exc}")

    elapsed = time.time() - start_time
    print()
    print("Repair complete.")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    print(f"Elapsed seconds: {elapsed:.2f}")


if __name__ == "__main__":
    main()
