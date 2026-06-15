#!/usr/bin/env python3
"""
Manually update unique_player and derived new_players for one date.

Rules:
- Update exactly four existing game_daily_metrics rows for one date.
- Require previous-day rows with non-NULL unique_player for all four games.
- Preview all updates before writing.
- Apply all updates in one transaction, or write nothing.
"""

from datetime import datetime, timedelta

import mysql.connector
from mysql.connector import Error

from db_config import get_db_config


GAMES = [
    (2073620, "Arena Breakout: Infinite"),
    (2507950, "Delta Force"),
    (3478050, "Road to Empress"),
    (3104410, "Terminull Brigade"),
]


def parse_date_input(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")


def parse_int_input(label, value):
    try:
        parsed = int(value)
    except ValueError:
        raise ValueError(f"{label} must be an integer.")
    if parsed < 0:
        raise ValueError(f"{label} must be >= 0.")
    return parsed


def collect_inputs():
    target_date = parse_date_input(input("Date (YYYY-MM-DD): ").strip())
    unique_players = {}

    for app_id, game_name in GAMES:
        raw_value = input(f"{game_name} unique_player: ").strip()
        unique_players[app_id] = parse_int_input(f"{game_name} unique_player", raw_value)

    return target_date, unique_players


def load_rows(cursor, target_date):
    previous_date = target_date - timedelta(days=1)
    app_ids = [app_id for app_id, _ in GAMES]
    placeholders = ", ".join(["%s"] * len(app_ids))

    cursor.execute(
        f"""
        SELECT steam_app_id, game_name, stat_date, unique_player, new_players
        FROM game_daily_metrics
        WHERE stat_date IN (%s, %s)
          AND steam_app_id IN ({placeholders})
        """,
        (target_date, previous_date, *app_ids),
    )

    rows = {}
    for row in cursor.fetchall():
        rows[(row["steam_app_id"], row["stat_date"])] = row
    return rows


def build_update_plan(rows, target_date, unique_players):
    previous_date = target_date - timedelta(days=1)
    missing_errors = []
    update_plan = []

    for app_id, game_name in GAMES:
        today_row = rows.get((app_id, target_date))
        previous_row = rows.get((app_id, previous_date))

        if today_row is None:
            missing_errors.append(f"{game_name}: target row missing for {target_date}")
            continue

        if previous_row is None:
            missing_errors.append(f"{game_name}: previous row missing for {previous_date}")
            continue

        previous_unique = previous_row.get("unique_player")
        if previous_unique is None:
            missing_errors.append(f"{game_name}: previous unique_player is NULL for {previous_date}")
            continue

        input_unique = unique_players[app_id]
        new_players = max(0, input_unique - int(previous_unique))
        update_plan.append(
            {
                "steam_app_id": app_id,
                "game_name": game_name,
                "stat_date": target_date,
                "old_unique_player": today_row.get("unique_player"),
                "old_new_players": today_row.get("new_players"),
                "input_unique_player": input_unique,
                "previous_unique_player": int(previous_unique),
                "new_players": new_players,
            }
        )

    if missing_errors:
        raise ValueError("\n".join(missing_errors))

    return update_plan


def print_preview(update_plan):
    print("\nUpdate preview:")
    print("-" * 100)
    for item in update_plan:
        print(
            f"{item['game_name']} ({item['steam_app_id']}) | "
            f"old unique_player={item['old_unique_player']} -> {item['input_unique_player']} | "
            f"previous unique_player={item['previous_unique_player']} | "
            f"old new_players={item['old_new_players']} -> {item['new_players']}"
        )
    print("-" * 100)


def apply_updates(connection, update_plan):
    cursor = connection.cursor()
    try:
        for item in update_plan:
            cursor.execute(
                """
                UPDATE game_daily_metrics
                SET unique_player = %s,
                    new_players = %s
                WHERE steam_app_id = %s
                  AND stat_date = %s
                """,
                (
                    item["input_unique_player"],
                    item["new_players"],
                    item["steam_app_id"],
                    item["stat_date"],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Expected to update 1 row for {item['game_name']} on {item['stat_date']}, "
                    f"updated {cursor.rowcount} rows."
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    print("=" * 80)
    print("Update unique_player and new_players")
    print("=" * 80)
    print("This script updates four existing game_daily_metrics rows in one transaction.")
    print("It requires previous-day unique_player values for all four games.")
    print()

    try:
        target_date, unique_players = collect_inputs()
        connection = mysql.connector.connect(**get_db_config())
        cursor = connection.cursor(dictionary=True)

        try:
            rows = load_rows(cursor, target_date)
            update_plan = build_update_plan(rows, target_date, unique_players)
        finally:
            cursor.close()

        print_preview(update_plan)
        confirm = input("\nProceed with database update? (y/N): ").strip().lower()
        if confirm != "y":
            print("Cancelled. No database changes were made.")
            return

        apply_updates(connection, update_plan)
        print("\nSuccess: updated unique_player and new_players for all four games.")

    except (ValueError, Error, RuntimeError) as exc:
        print(f"\n[ERROR] {exc}")
        print("No database changes were made.")
        raise SystemExit(1)
    finally:
        try:
            if connection and connection.is_connected():
                connection.close()
        except NameError:
            pass


if __name__ == "__main__":
    main()
