import mysql.connector
from mysql.connector import Error
import json
from datetime import date
import os
import argparse

def _parse_args():
    parser = argparse.ArgumentParser(description="Test MySQL database connection and basic operations")
    parser.add_argument("--host", default=os.environ.get("STEAMWORKS_DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STEAMWORKS_DB_PORT", 3306)))
    parser.add_argument("--db", default=os.environ.get("STEAMWORKS_DB_NAME", "steamworks_crawler"))
    parser.add_argument("--user", default=os.environ.get("STEAMWORKS_DB_USER", "root"))
    parser.add_argument("--password", default=os.environ.get("STEAMWORKS_DB_PASSWORD", "Zh1149191843!"))
    parser.add_argument("--table", default=os.environ.get("STEAMWORKS_DB_TABLE", "game_daily_metrics"))
    return parser.parse_args()

def test_database_connection():
    """Test MySQL database connection and basic operations"""
    
    args = _parse_args()
    # Database configuration
    config = {
        'host': args.host,
        'port': args.port,
        'database': args.db,
        'user': args.user,
        'password': args.password
    }
    
    connection = None
    cursor = None
    
    try:
        print("=== Database Connection Test ===")
        
        # Test 1: Connect to MySQL
        print("1. Testing database connection...")
        connection = mysql.connector.connect(**config)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"✓ Successfully connected to MySQL Server version {db_info}")
            
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            database_name = cursor.fetchone()[0]
            print(f"✓ Connected to database: {database_name}")
        
        # Test 2: Check if table exists
        print("\n2. Checking if table exists...")
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (args.db, args.table)
        )
        table_exists = cursor.fetchone()[0]
        if table_exists:
            print(f"✓ Table '{args.table}' exists")
        else:
            print(f"✗ Table '{args.table}' not found in database '{args.db}'")
            return False
        
        # Test 3: Show table structure
        print("\n3. Table structure:")
        cursor.execute(f"DESCRIBE {args.table}")
        columns = cursor.fetchall()
        
        for column in columns:
            print(f"  - {column[0]}: {column[1]}")
        column_names = {c[0] for c in columns}
        
        # If this is the legacy PoC table with specific columns, run insert/retrieve tests
        legacy_required = {"date", "dau", "pcu", "unique_users_lifetime"}
        if legacy_required.issubset(column_names):
            print("\n4. Testing data insertion (legacy PoC table detected)...")
            test_data = {
                'date': date.today(),
                'dau': 1000,
                'pcu': 150,
                'unique_users_lifetime': 99834,
                'new_users': 50,
                'paid_users': 25,
                'retention': json.dumps({'day1': 0.75, 'day7': 0.45, 'day30': 0.25}),
                'median_playtime': 2.5,
                'playtime_breakdown': json.dumps({'0-1h': 0.3, '1-5h': 0.4, '5h+': 0.3}),
                'revenue': 1250.50,
                'arpu': 1.25,
                'arppu': 50.02,
                'ltv': 15.75,
                'new_users_percentage': 5.0,
                'paying_users_percentage': 2.5,
                'wishlist_conversion': 12.5,
                'wishlist_outstanding': 500,
                'wishlist_stats': json.dumps({'total': 1000, 'converted': 125}),
                'key_activations': 75,
                'download_conversion': 8.5,
                'regional_revenue': json.dumps({'US': 500, 'EU': 400, 'Asia': 350.50}),
                'regional_players': json.dumps({'US': 400, 'EU': 350, 'Asia': 250}),
                'regional_downloads': json.dumps({'US': 45, 'EU': 40, 'Asia': 35}),
                'in_game_breakdown': json.dumps({'missions': 0.4, 'multiplayer': 0.35, 'customization': 0.25})
            }
            insert_query = f"""
            INSERT INTO {args.table} (
                date, dau, pcu, unique_users_lifetime, new_users, paid_users,
                retention, median_playtime, playtime_breakdown, revenue, arpu, arppu, ltv,
                new_users_percentage, paying_users_percentage, wishlist_conversion,
                wishlist_outstanding, wishlist_stats, key_activations, download_conversion,
                regional_revenue, regional_players, regional_downloads, in_game_breakdown
            ) VALUES (
                %(date)s, %(dau)s, %(pcu)s, %(unique_users_lifetime)s, %(new_users)s, %(paid_users)s,
                %(retention)s, %(median_playtime)s, %(playtime_breakdown)s, %(revenue)s, %(arpu)s, %(arppu)s, %(ltv)s,
                %(new_users_percentage)s, %(paying_users_percentage)s, %(wishlist_conversion)s,
                %(wishlist_outstanding)s, %(wishlist_stats)s, %(key_activations)s, %(download_conversion)s,
                %(regional_revenue)s, %(regional_players)s, %(regional_downloads)s, %(in_game_breakdown)s
            )
            """
            cursor.execute(insert_query, test_data)
            connection.commit()
            print("✓ Test data inserted successfully")

            print("\n5. Testing data retrieval...")
            cursor.execute(f"SELECT * FROM {args.table} WHERE date = %s", (date.today(),))
            record = cursor.fetchone()
            if record:
                print("✓ Test data retrieved successfully")
            else:
                print("✗ Failed to retrieve test data")

            print("\n6. Testing record count...")
            cursor.execute(f"SELECT COUNT(*) FROM {args.table}")
            count = cursor.fetchone()[0]
            print(f"✓ Total records in table: {count}")
        else:
            # Non-legacy table (e.g., game_daily_metrics). Do safe read-only checks.
            print("\n4. Skipping insertion (non-legacy schema). Running read-only checks...")
            cursor.execute(f"SELECT COUNT(*) FROM {args.table}")
            row_count = cursor.fetchone()[0]
            print(f"✓ Row count in '{args.table}': {row_count}")
            sample_cols = [c for c in [
                "steam_app_id", "game_name", "stat_date", "dau", "pcu", "daily_total_revenue"
            ] if c in column_names]
            if sample_cols:
                cols_csv = ", ".join(sample_cols)
                cursor.execute(f"SELECT {cols_csv} FROM {args.table} ORDER BY stat_date DESC LIMIT 3")
                rows = cursor.fetchall()
                print(f"✓ Sample rows ({len(rows)}):")
                for r in rows:
                    print(f"  - {r}")
            else:
                print("⚠️  Could not find common sample columns to display.")
        
        print("\n=== All Database Tests Passed! ===")
        return True
        
    except Error as e:
        print(f"✗ Database error: {e}")
        return False
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
        
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            print("\n✓ Database connection closed")

if __name__ == "__main__":
    success = test_database_connection()
    
    if success:
        print("\n🎉 Database connection test completed successfully!")
        print("Your MySQL database is ready for the SteamWorks crawler.")
    else:
        print("\n❌ Database connection test failed.")
        print("Please check your MySQL credentials and try again.") 