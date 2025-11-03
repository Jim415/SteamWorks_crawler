"""
Quick script to check what marketing data was actually saved
"""
import mysql.connector
import json

db_config = {
    'host': 'localhost',
    'port': 3306,
    'database': 'steamworks_crawler',
    'user': 'root',
    'password': 'Zh1149191843!'
}

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Check the latest marketing data
    cursor.execute("""
        SELECT stat_date, total_impressions, total_visits, 
               total_click_through_rate, owner_visits,
               CASE 
                   WHEN homepage_breakdown IS NULL THEN 'NULL'
                   ELSE CONCAT('JSON with ', JSON_LENGTH(homepage_breakdown), ' items')
               END as homepage_status,
               CASE 
                   WHEN all_source_breakdown IS NULL THEN 'NULL'
                   ELSE CONCAT('JSON with ', JSON_LENGTH(all_source_breakdown), ' items')
               END as source_status
        FROM delta_force_daily_marketing
        ORDER BY stat_date DESC
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    
    print("\n" + "="*80)
    print("Latest Marketing Data in Database")
    print("="*80)
    
    for row in rows:
        print(f"\nDate: {row['stat_date']}")
        print(f"  Total Impressions: {row['total_impressions']}")
        print(f"  Total Visits: {row['total_visits']}")
        print(f"  Click-Through Rate: {row['total_click_through_rate']}")
        print(f"  Owner Visits: {row['owner_visits']}")
        print(f"  Homepage Breakdown: {row['homepage_status']}")
        print(f"  All Source Breakdown: {row['source_status']}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")








