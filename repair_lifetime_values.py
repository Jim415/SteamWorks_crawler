#!/usr/bin/env python3
"""
Repair missing lifetime values in game_daily_metrics.

The script scans a user-provided date range and repairs NULL lifetime values using:

    today_lifetime = previous_day_lifetime + daily_value

If today's daily value is NULL, the previous day's daily value is used.
Existing lifetime values are never overwritten.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

import mysql.connector
from mysql.connector import Error

from db_config import get_db_config


GAMES = [
    (2073620, "Arena Breakout: Infinite"),
    (2507950, "Delta Force"),
    (3478050, "Road to Empress"),
    (3104410, "Terminull Brigade"),
]

REPAIR_PAIRS = [
    {
        "lifetime_col": "lifetime_total_revenue",
        "daily_col": "daily_total_revenue",
        "value_type": "decimal",
    },
    {
        "lifetime_col": "lifetime_total_units",
        "daily_col": "daily_units",
        "value_type": "int",
    },
    {
        "lifetime_col": "wishlist",
        "daily_col": "wishlist_additions",
        "value_type": "int",
    },
]


def parse_date_input(date_str):
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYYMMDD.")


def normalize_value(value, value_type):
    if value is None:
        return None
    if value_type == "decimal":
        return Decimal(value).quantize(Decimal("0.01"))
    return int(value)


def load_rows(cursor, start_date, end_date):
    app_ids = [app_id for app_id, _ in GAMES]
    placeholders = ", ".join(["%s"] * len(app_ids))
    columns = [
        "steam_app_id",
        "game_name",
        "stat_date",
        "lifetime_total_revenue",
        "daily_total_revenue",
        "lifetime_total_units",
        "daily_units",
        "wishlist",
        "wishlist_additions",
    ]

    cursor.execute(
        f"""
        SELECT {", ".join(columns)}
        FROM game_daily_metrics
        WHERE stat_date BETWEEN %s AND %s
          AND steam_app_id IN ({placeholders})
        ORDER BY steam_app_id, stat_date
        """,
        (start_date - timedelta(days=1), end_date, *app_ids),
    )
    return cursor.fetchall()


def group_rows_by_game(rows):
    by_game = {}
    for row in rows:
        app_id = row["steam_app_id"]
        by_game.setdefault(
            app_id,
            {
                "game_name": row["game_name"],
                "rows": {},
            },
        )
        by_game[app_id]["rows"][row["stat_date"]] = dict(row)
    return by_game


def build_repair_plan(by_game, start_date, end_date):
    updates = []
    blockers = []

    for app_id, expected_game_name in GAMES:
        game_data = by_game.get(app_id)
        if not game_data:
            blockers.append(
                {
                    "game_name": expected_game_name,
                    "steam_app_id": app_id,
                    "stat_date": None,
                    "column": None,
                    "reason": "no rows found for game in scan window",
                }
            )
            continue

        game_name = game_data["game_name"] or expected_game_name
        date_map = game_data["rows"]

        for stat_date in sorted(date_map):
            if stat_date < start_date or stat_date > end_date:
                continue

            row = date_map[stat_date]
            previous_date = stat_date - timedelta(days=1)
            previous_row = date_map.get(previous_date)

            for pair in REPAIR_PAIRS:
                lifetime_col = pair["lifetime_col"]
                daily_col = pair["daily_col"]
                value_type = pair["value_type"]

                if row.get(lifetime_col) is not None:
                    continue

                if previous_row is None:
                    blockers.append(
                        {
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": stat_date,
                            "column": lifetime_col,
                            "reason": f"previous row missing for {previous_date}",
                        }
                    )
                    continue

                previous_lifetime = previous_row.get(lifetime_col)
                if previous_lifetime is None:
                    blockers.append(
                        {
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": stat_date,
                            "column": lifetime_col,
                            "reason": f"previous {lifetime_col} is NULL for {previous_date}",
                        }
                    )
                    continue

                daily_value = row.get(daily_col)
                daily_source = "today"
                if daily_value is None:
                    daily_value = previous_row.get(daily_col)
                    daily_source = "previous_day"

                if daily_value is None:
                    blockers.append(
                        {
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": stat_date,
                            "column": lifetime_col,
                            "reason": f"{daily_col} is NULL for both {stat_date} and {previous_date}",
                        }
                    )
                    continue

                repaired_value = normalize_value(previous_lifetime + daily_value, value_type)
                row[lifetime_col] = repaired_value
                updates.append(
                    {
                        "game_name": game_name,
                        "steam_app_id": app_id,
                        "stat_date": stat_date,
                        "lifetime_col": lifetime_col,
                        "daily_col": daily_col,
                        "previous_date": previous_date,
                        "previous_lifetime": normalize_value(previous_lifetime, value_type),
                        "daily_value": normalize_value(daily_value, value_type),
                        "daily_source": daily_source,
                        "repaired_value": repaired_value,
                    }
                )

    return updates, blockers


def print_summary(updates, blockers):
    update_counts = defaultdict(int)
    previous_daily_counts = defaultdict(int)
    blocker_counts = defaultdict(int)

    for update in updates:
        key = (update["game_name"], update["lifetime_col"])
        update_counts[key] += 1
        if update["daily_source"] == "previous_day":
            previous_daily_counts[key] += 1

    for blocker in blockers:
        key = (blocker["game_name"], blocker["column"], blocker["reason"])
        blocker_counts[key] += 1

    print("\nRepair summary:")
    print("-" * 100)
    if updates:
        for (game_name, lifetime_col), count in sorted(update_counts.items()):
            prev_daily_count = previous_daily_counts.get((game_name, lifetime_col), 0)
            print(
                f"{game_name} | {lifetime_col}: {count} cells repairable "
                f"({prev_daily_count} using previous-day daily value)"
            )
    else:
        print("No repairable NULL lifetime values found.")

    if blockers:
        print("\nBlocker summary:")
        for (game_name, column, reason), count in sorted(blocker_counts.items()):
            print(f"{game_name} | {column}: {count} blocked - {reason}")
    print("-" * 100)


def print_update_details(updates):
    if not updates:
        return

    print("\nRepair details:")
    print("-" * 100)
    for update in updates:
        print(
            f"{update['stat_date']} | {update['game_name']} ({update['steam_app_id']}) | "
            f"{update['lifetime_col']} = {update['previous_lifetime']} + "
            f"{update['daily_value']} ({update['daily_col']} source={update['daily_source']}) "
            f"-> {update['repaired_value']}"
        )
    print("-" * 100)


def apply_updates(connection, updates):
    cursor = connection.cursor()
    try:
        for update in updates:
            lifetime_col = update["lifetime_col"]
            query = f"""
                UPDATE game_daily_metrics
                SET {lifetime_col} = %s
                WHERE steam_app_id = %s
                  AND stat_date = %s
                  AND {lifetime_col} IS NULL
            """
            cursor.execute(
                query,
                (
                    update["repaired_value"],
                    update["steam_app_id"],
                    update["stat_date"],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Expected to update 1 cell for {update['game_name']} "
                    f"{update['stat_date']} {lifetime_col}, updated {cursor.rowcount}."
                )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    print("=" * 80)
    print("Repair Missing Lifetime Values")
    print("=" * 80)
    start_input = input("Enter start date (YYYYMMDD): ").strip()
    if not start_input:
        print("[ERROR] No start date provided.")
        raise SystemExit(1)

    end_input = input("Enter end date (YYYYMMDD): ").strip()
    if not end_input:
        print("[ERROR] No end date provided.")
        raise SystemExit(1)

    try:
        start_date = parse_date_input(start_input)
        end_date = parse_date_input(end_input)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)

    if start_date > end_date:
        print("[ERROR] Start date must be earlier than or equal to end date.")
        raise SystemExit(1)

    print(f"Scan range: {start_date} to {end_date}")
    print("Pairs:")
    for pair in REPAIR_PAIRS:
        print(f"  {pair['lifetime_col']} <- previous lifetime + {pair['daily_col']}")
    print("If today's daily value is NULL, previous day's daily value is used.")
    print("Existing lifetime values are never overwritten.")
    print()

    connection = None
    try:
        connection = mysql.connector.connect(**get_db_config())
        cursor = connection.cursor(dictionary=True)
        try:
            rows = load_rows(cursor, start_date, end_date)
        finally:
            cursor.close()

        by_game = group_rows_by_game(rows)
        updates, blockers = build_repair_plan(by_game, start_date, end_date)

        print_summary(updates, blockers)
        print_update_details(updates)

        if not updates:
            print("\nNothing to update.")
            return

        confirm = input("\nProceed with database update? (y/N): ").strip().lower()
        if confirm != "y":
            print("Cancelled. No database changes were made.")
            return

        apply_updates(connection, updates)
        print(f"\nSuccess: repaired {len(updates)} lifetime cells.")

    except (Error, RuntimeError, ValueError) as exc:
        print(f"\n[ERROR] {exc}")
        print("No database changes were made.")
        raise SystemExit(1)
    finally:
        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
