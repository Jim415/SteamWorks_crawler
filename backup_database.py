#!/usr/bin/env python3
"""Export steamworks_crawler database to a local SQL file."""

import argparse
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import mysql.connector

from db_config import get_db_config


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return f"'{value.isoformat()}'"
    if isinstance(value, (bytes, bytearray)):
        return "0x" + value.hex()
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{text}'"


def export_database(output_path: Path):
    db_config = get_db_config()
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()

    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    lines = [
        "-- SteamWorks database backup",
        f"-- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"-- Host: {db_config['host']}:{db_config['port']}",
        f"-- Database: {db_config['database']}",
        "",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS=0;",
        "",
    ]

    for table in tables:
        cursor.execute(f"SHOW CREATE TABLE `{table}`")
        create_sql = cursor.fetchone()[1]
        lines.extend([f"DROP TABLE IF EXISTS `{table}`;", f"{create_sql};", ""])

        cursor.execute(f"SELECT * FROM `{table}`")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        if not rows:
            lines.append(f"-- Table `{table}`: 0 rows")
            lines.append("")
            continue

        column_list = ", ".join(f"`{column}`" for column in columns)
        lines.append(f"-- Table `{table}`: {len(rows)} rows")
        for row in rows:
            values = ", ".join(sql_literal(value) for value in row)
            lines.append(f"INSERT INTO `{table}` ({column_list}) VALUES ({values});")
        lines.append("")

    lines.append("SET FOREIGN_KEY_CHECKS=1;")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    cursor.close()
    connection.close()
    return output_path, tables


def main():
    parser = argparse.ArgumentParser(description="Backup steamworks_crawler database to SQL.")
    parser.add_argument(
        "--output",
        help="Output .sql path (default: backups/steamworks_crawler_YYYYMMDD_HHMMSS.sql)",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(__file__).resolve().parent / "backups" / f"steamworks_crawler_{stamp}.sql"

    output_path, tables = export_database(output_path)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Backup saved: {output_path}")
    print(f"Tables: {', '.join(tables)}")
    print(f"Size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
