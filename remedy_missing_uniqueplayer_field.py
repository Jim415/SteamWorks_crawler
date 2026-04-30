"""
Remedy missing unique_player values in game_daily_metrics.

Rules:
- Ask user for start date and end date (YYYYMMDD)
- Process all games for the inclusive date range
- Only update existing rows where unique_player is NULL
- Use previous/next available unique_player anchors for that game
- Fill iteratively with floor rounding
- Only fill when missing gap size is <= 7 days
- When unique_player is filled, set new_players = today's unique_player minus previous calendar day's
  unique_player (same logic as steamworks_crawler: no prev row -> new_players = unique_player;
  prev NULL -> new_players NULL; else max(0, delta))
"""

from datetime import datetime, timedelta
import math
import logging
import sys
import mysql.connector
from mysql.connector import Error
from db_config import get_db_config


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('remedy_missing_data.log'),
        logging.StreamHandler()
    ]
)


def parse_date_input(date_str):
    """Parse YYYYMMDD format to date object."""
    try:
        return datetime.strptime(date_str, '%Y%m%d').date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYYMMDD (e.g., 20250227)")


def get_rows_by_game(cursor):
    """Load all rows ordered by game/date for anchor lookup and in-memory filling."""
    cursor.execute(
        """
        SELECT steam_app_id, game_name, stat_date, unique_player
        FROM game_daily_metrics
        ORDER BY steam_app_id, stat_date
        """
    )
    rows = cursor.fetchall()
    by_game = {}
    for app_id, game_name, stat_date, unique_player in rows:
        by_game.setdefault(app_id, {"game_name": game_name, "rows": []})
        by_game[app_id]["rows"].append(
            {"stat_date": stat_date, "unique_player": unique_player}
        )
    return by_game


def find_prev_known(rows, idx):
    j = idx - 1
    while j >= 0:
        if rows[j]["unique_player"] is not None:
            return j
        j -= 1
    return None


def find_next_known(rows, idx):
    j = idx + 1
    while j < len(rows):
        if rows[j]["unique_player"] is not None:
            return j
        j += 1
    return None


def count_remaining_missing(rows, idx, right_idx):
    """Count NULL rows from current idx to right anchor (exclusive)."""
    count = 0
    for k in range(idx, right_idx):
        if rows[k]["unique_player"] is None:
            count += 1
    return count


def compute_new_players_for_filled_row(date_map, stat_date, new_unique_player):
    """
    Match steamworks_crawler.save_to_database: new_players from previous day's unique_player.
    """
    prev_date = stat_date - timedelta(days=1)
    prev_row = date_map.get(prev_date)
    if prev_row is None:
        return int(new_unique_player)
    pu = prev_row["unique_player"]
    if pu is None:
        return None
    delta = int(new_unique_player) - int(pu)
    return delta if delta >= 0 else 0


def remedy_unique_player_for_window(by_game, start_date, end_date):
    """
    Compute fills for NULL unique_player values in [start_date, end_date].
    Returns list of (app_id, stat_date, new_unique_player, new_players_or_none, reason).
    """
    updates = []
    skipped = []

    for app_id, game_data in by_game.items():
        rows = game_data["rows"]
        date_map = {r["stat_date"]: r for r in rows}
        for idx, row in enumerate(rows):
            stat_date = row["stat_date"]
            if stat_date < start_date or stat_date > end_date:
                continue
            if row["unique_player"] is not None:
                continue

            left_idx = find_prev_known(rows, idx)
            right_idx = find_next_known(rows, idx)
            if left_idx is None or right_idx is None:
                skipped.append((app_id, stat_date, "missing left or right anchor"))
                continue

            gap_days = (rows[right_idx]["stat_date"] - rows[left_idx]["stat_date"]).days - 1
            if gap_days <= 0 or gap_days > 7:
                skipped.append((app_id, stat_date, f"gap_days={gap_days} out of allowed range"))
                continue

            left_val = float(rows[left_idx]["unique_player"])
            right_val = float(rows[right_idx]["unique_player"])

            if right_val < left_val:
                skipped.append((app_id, stat_date, "right anchor smaller than left anchor"))
                continue

            remaining_missing = count_remaining_missing(rows, idx, right_idx)
            if remaining_missing <= 0:
                skipped.append((app_id, stat_date, "no remaining missing rows in gap"))
                continue

            step = (right_val - left_val) / (remaining_missing + 1)
            new_val = int(math.floor(left_val + step))

            # Keep monotonic progression bounded by anchors.
            if new_val < int(left_val):
                new_val = int(left_val)
            if new_val > int(right_val):
                new_val = int(right_val)

            rows[idx]["unique_player"] = new_val
            new_players_val = compute_new_players_for_filled_row(date_map, stat_date, new_val)
            updates.append(
                (
                    app_id,
                    stat_date,
                    new_val,
                    new_players_val,
                    f"left={int(left_val)}, right={int(right_val)}, gap_days={gap_days}",
                )
            )

    return updates, skipped


def apply_updates(cursor, updates):
    for app_id, stat_date, new_val, new_players_val, _ in updates:
        if new_players_val is not None:
            cursor.execute(
                """
                UPDATE game_daily_metrics
                SET unique_player = %s,
                    new_players = %s
                WHERE steam_app_id = %s
                  AND stat_date = %s
                  AND unique_player IS NULL
                """,
                (new_val, new_players_val, app_id, stat_date),
            )
        else:
            cursor.execute(
                """
                UPDATE game_daily_metrics
                SET unique_player = %s
                WHERE steam_app_id = %s
                  AND stat_date = %s
                  AND unique_player IS NULL
                """,
                (new_val, app_id, stat_date),
            )


def main():
    print("=" * 80)
    print("Remedy Missing unique_player Script")
    print("=" * 80)
    print("This script fills NULL unique_player values for an inclusive date range.")
    print("Rules: floor rounding, max gap size 7 days, all games.")
    print("Also sets new_players = today's unique_player - previous day's (when computable).")
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

    if end_date < start_date:
        print("[ERROR] End date cannot be earlier than start date.")
        sys.exit(1)

    print(f"Window: {start_date} to {end_date} (inclusive)")

    confirm = input("Proceed with DB update? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    db_config = get_db_config()

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        by_game = get_rows_by_game(cursor)
        updates, skipped = remedy_unique_player_for_window(by_game, start_date, end_date)

        if updates:
            apply_updates(cursor, updates)
            connection.commit()

        print("\n" + "=" * 80)
        print("Remedy Summary")
        print("=" * 80)
        print(f"Updated rows: {len(updates)}")
        print(f"Skipped rows: {len(skipped)}")

        if updates:
            print("\nUpdated entries:")
            for app_id, stat_date, new_val, new_players_val, reason in updates:
                np_str = str(new_players_val) if new_players_val is not None else "NULL"
                print(
                    f"  app_id={app_id} date={stat_date} unique_player={new_val} "
                    f"new_players={np_str} ({reason})"
                )

        if skipped:
            print("\nSkipped entries:")
            for app_id, stat_date, reason in skipped:
                print(f"  app_id={app_id} date={stat_date} reason={reason}")

        print("=" * 80)

    except Error as exc:
        if connection:
            connection.rollback()
        print(f"[ERROR] Database error: {exc}")
        sys.exit(1)
    except Exception as exc:
        if connection:
            connection.rollback()
        print(f"[ERROR] Unexpected error: {exc}")
        sys.exit(1)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
