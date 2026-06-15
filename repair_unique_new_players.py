#!/usr/bin/env python3
"""
Repair missing unique_player and new_players values in game_daily_metrics.

Rules:
- Repair a user-provided inclusive date range.
- Read the whole table so interpolation can use anchors outside the range.
- First fill NULL unique_player values by linear interpolation between the
  nearest previous and next non-NULL unique_player values for the same game.
- Then fill NULL new_players values from today's unique_player minus the
  previous calendar day's unique_player for the same game.
- Existing non-NULL values are never overwritten.
- Write all updates in one transaction after user confirmation.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from math import floor

import mysql.connector
from mysql.connector import Error

from db_config import get_db_config


def parse_date_input(date_str):
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYYMMDD.")


def load_rows(cursor):
    cursor.execute(
        """
        SELECT steam_app_id, game_name, stat_date, unique_player, new_players
        FROM game_daily_metrics
        ORDER BY steam_app_id, stat_date
        """
    )
    return cursor.fetchall()


def group_rows_by_game(rows):
    by_game = {}
    for row in rows:
        app_id = row["steam_app_id"]
        by_game.setdefault(app_id, {"game_name": row["game_name"], "rows": []})
        by_game[app_id]["rows"].append(dict(row))
    return by_game


def is_in_target_range(stat_date, start_date, end_date):
    return start_date <= stat_date <= end_date


def interpolate_unique_players(by_game, start_date, end_date):
    updates = []
    blockers = []
    out_of_range = []

    for app_id, game_data in sorted(by_game.items()):
        game_name = game_data["game_name"]
        rows = game_data["rows"]
        idx = 0

        while idx < len(rows):
            if rows[idx]["unique_player"] is not None:
                idx += 1
                continue

            start_idx = idx
            while idx < len(rows) and rows[idx]["unique_player"] is None:
                idx += 1
            end_idx = idx - 1

            repair_indices = []
            for row_idx in range(start_idx, end_idx + 1):
                stat_date = rows[row_idx]["stat_date"]
                if is_in_target_range(stat_date, start_date, end_date):
                    repair_indices.append(row_idx)
                else:
                    out_of_range.append(
                        {
                            "type": "unique_player",
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": stat_date,
                            "reason": "outside target date range",
                        }
                    )

            if not repair_indices:
                continue

            left_idx = start_idx - 1
            right_idx = idx
            if left_idx < 0 or right_idx >= len(rows):
                for row_idx in repair_indices:
                    blockers.append(
                        {
                            "type": "unique_player",
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": rows[row_idx]["stat_date"],
                            "reason": "missing left or right anchor",
                        }
                    )
                continue

            left_row = rows[left_idx]
            right_row = rows[right_idx]
            left_unique = left_row["unique_player"]
            right_unique = right_row["unique_player"]

            if left_unique is None or right_unique is None:
                for row_idx in repair_indices:
                    blockers.append(
                        {
                            "type": "unique_player",
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": rows[row_idx]["stat_date"],
                            "reason": "missing left or right anchor",
                        }
                    )
                continue

            if int(right_unique) < int(left_unique):
                for row_idx in repair_indices:
                    blockers.append(
                        {
                            "type": "unique_player",
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": rows[row_idx]["stat_date"],
                            "reason": "right anchor smaller than left anchor",
                        }
                    )
                continue

            missing_count = end_idx - start_idx + 1
            step = (int(right_unique) - int(left_unique)) / (missing_count + 1)

            for offset, row_idx in enumerate(range(start_idx, end_idx + 1), start=1):
                new_unique = int(floor(int(left_unique) + step * offset))
                rows[row_idx]["unique_player"] = new_unique

                if row_idx in repair_indices:
                    updates.append(
                        {
                            "game_name": game_name,
                            "steam_app_id": app_id,
                            "stat_date": rows[row_idx]["stat_date"],
                            "new_unique_player": new_unique,
                            "left_date": left_row["stat_date"],
                            "left_unique_player": int(left_unique),
                            "right_date": right_row["stat_date"],
                            "right_unique_player": int(right_unique),
                            "gap_missing_count": missing_count,
                        }
                    )

    return updates, blockers, out_of_range


def compute_new_players(by_game, start_date, end_date):
    updates = []
    blockers = []
    out_of_range = []

    for app_id, game_data in sorted(by_game.items()):
        game_name = game_data["game_name"]
        rows = game_data["rows"]
        date_map = {row["stat_date"]: row for row in rows}

        for row in rows:
            stat_date = row["stat_date"]
            if row["new_players"] is not None:
                continue

            if not is_in_target_range(stat_date, start_date, end_date):
                out_of_range.append(
                    {
                        "type": "new_players",
                        "game_name": game_name,
                        "steam_app_id": app_id,
                        "stat_date": stat_date,
                        "reason": "outside target date range",
                    }
                )
                continue

            today_unique = row["unique_player"]
            if today_unique is None:
                blockers.append(
                    {
                        "type": "new_players",
                        "game_name": game_name,
                        "steam_app_id": app_id,
                        "stat_date": stat_date,
                        "reason": "today unique_player missing",
                    }
                )
                continue

            previous_date = stat_date - timedelta(days=1)
            previous_row = date_map.get(previous_date)
            if previous_row is None:
                blockers.append(
                    {
                        "type": "new_players",
                        "game_name": game_name,
                        "steam_app_id": app_id,
                        "stat_date": stat_date,
                        "reason": f"previous calendar row missing for {previous_date}",
                    }
                )
                continue

            previous_unique = previous_row["unique_player"]
            if previous_unique is None:
                blockers.append(
                    {
                        "type": "new_players",
                        "game_name": game_name,
                        "steam_app_id": app_id,
                        "stat_date": stat_date,
                        "reason": f"previous unique_player missing for {previous_date}",
                    }
                )
                continue

            new_players = max(0, int(today_unique) - int(previous_unique))
            row["new_players"] = new_players
            updates.append(
                {
                    "game_name": game_name,
                    "steam_app_id": app_id,
                    "stat_date": stat_date,
                    "new_players": new_players,
                    "today_unique_player": int(today_unique),
                    "previous_date": previous_date,
                    "previous_unique_player": int(previous_unique),
                }
            )

    return updates, blockers, out_of_range


def print_summary(unique_updates, new_players_updates, blockers, out_of_range, start_date, end_date):
    print("\nRepair summary:")
    print("-" * 100)
    print(f"Target date range: {start_date} to {end_date}")
    print(f"unique_player cells repairable: {len(unique_updates)}")
    print(f"new_players cells repairable: {len(new_players_updates)}")
    print(f"blockers: {len(blockers)}")
    print(f"out-of-range missing cells ignored: {len(out_of_range)}")

    unique_counts = defaultdict(int)
    new_counts = defaultdict(int)
    blocker_counts = defaultdict(int)
    out_of_range_counts = defaultdict(int)

    for update in unique_updates:
        unique_counts[update["game_name"]] += 1
    for update in new_players_updates:
        new_counts[update["game_name"]] += 1
    for blocker in blockers:
        key = (blocker["type"], blocker["game_name"], blocker["reason"])
        blocker_counts[key] += 1
    for item in out_of_range:
        key = (item["type"], item["game_name"], item["reason"])
        out_of_range_counts[key] += 1

    if unique_counts:
        print("\nunique_player updates by game:")
        for game_name, count in sorted(unique_counts.items()):
            print(f"  {game_name}: {count}")

    if new_counts:
        print("\nnew_players updates by game:")
        for game_name, count in sorted(new_counts.items()):
            print(f"  {game_name}: {count}")

    if blocker_counts:
        print("\nBlockers:")
        for (update_type, game_name, reason), count in sorted(blocker_counts.items()):
            print(f"  {update_type} | {game_name}: {count} - {reason}")

    if out_of_range_counts:
        print("\nOut-of-range missing cells ignored:")
        for (update_type, game_name, reason), count in sorted(out_of_range_counts.items()):
            print(f"  {update_type} | {game_name}: {count} - {reason}")

    print("-" * 100)


def print_details(unique_updates, new_players_updates):
    if unique_updates:
        print("\nunique_player repair details:")
        print("-" * 100)
        for update in unique_updates:
            print(
                f"{update['stat_date']} | {update['game_name']} ({update['steam_app_id']}) | "
                f"unique_player={update['new_unique_player']} "
                f"from {update['left_date']}:{update['left_unique_player']} -> "
                f"{update['right_date']}:{update['right_unique_player']} "
                f"across {update['gap_missing_count']} missing row(s)"
            )
        print("-" * 100)

    if new_players_updates:
        print("\nnew_players repair details:")
        print("-" * 100)
        for update in new_players_updates:
            print(
                f"{update['stat_date']} | {update['game_name']} ({update['steam_app_id']}) | "
                f"new_players={update['new_players']} "
                f"from {update['today_unique_player']} - "
                f"{update['previous_unique_player']} ({update['previous_date']})"
            )
        print("-" * 100)


def apply_updates(connection, unique_updates, new_players_updates):
    cursor = connection.cursor()
    try:
        for update in unique_updates:
            cursor.execute(
                """
                UPDATE game_daily_metrics
                SET unique_player = %s
                WHERE steam_app_id = %s
                  AND stat_date = %s
                  AND unique_player IS NULL
                """,
                (
                    update["new_unique_player"],
                    update["steam_app_id"],
                    update["stat_date"],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Expected to update 1 unique_player cell for {update['game_name']} "
                    f"{update['stat_date']}, updated {cursor.rowcount}."
                )

        for update in new_players_updates:
            cursor.execute(
                """
                UPDATE game_daily_metrics
                SET new_players = %s
                WHERE steam_app_id = %s
                  AND stat_date = %s
                  AND new_players IS NULL
                """,
                (
                    update["new_players"],
                    update["steam_app_id"],
                    update["stat_date"],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Expected to update 1 new_players cell for {update['game_name']} "
                    f"{update['stat_date']}, updated {cursor.rowcount}."
                )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    print("=" * 80)
    print("Repair unique_player and new_players")
    print("=" * 80)
    print("This script repairs a user-provided inclusive date range.")
    print("It reads the whole table to find interpolation anchors outside the range.")
    print("Existing non-NULL values are never overwritten.")
    print()

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

    connection = None
    try:
        connection = mysql.connector.connect(**get_db_config())
        cursor = connection.cursor(dictionary=True)
        try:
            rows = load_rows(cursor)
        finally:
            cursor.close()

        by_game = group_rows_by_game(rows)
        unique_updates, unique_blockers, unique_out_of_range = interpolate_unique_players(
            by_game, start_date, end_date
        )
        new_players_updates, new_blockers, new_out_of_range = compute_new_players(
            by_game, start_date, end_date
        )

        blockers = unique_blockers + new_blockers
        out_of_range = unique_out_of_range + new_out_of_range

        print_summary(unique_updates, new_players_updates, blockers, out_of_range, start_date, end_date)
        print_details(unique_updates, new_players_updates)

        if blockers:
            print("\n[ERROR] Blockers remain. No database changes were made.")
            raise SystemExit(1)

        if not unique_updates and not new_players_updates:
            print("\nNothing to update.")
            return

        confirm = input("\nProceed with database update? (y/N): ").strip().lower()
        if confirm != "y":
            print("Cancelled. No database changes were made.")
            return

        apply_updates(connection, unique_updates, new_players_updates)
        print(
            f"\nSuccess: repaired {len(unique_updates)} unique_player cells and "
            f"{len(new_players_updates)} new_players cells."
        )

    except (Error, RuntimeError) as exc:
        print(f"\n[ERROR] {exc}")
        print("No database changes were made.")
        raise SystemExit(1)
    finally:
        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
