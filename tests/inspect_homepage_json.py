"""
Inspect the actual homepage_breakdown JSON in the database
to see what data structure was saved
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
    
    # Get the latest marketing data
    cursor.execute("""
        SELECT stat_date, 
               homepage_breakdown,
               all_source_breakdown
        FROM delta_force_daily_marketing
        ORDER BY stat_date DESC
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    
    if row:
        print("="*80)
        print(f"Latest Marketing Data: {row['stat_date']}")
        print("="*80)
        
        # Inspect homepage_breakdown
        if row['homepage_breakdown']:
            homepage_data = json.loads(row['homepage_breakdown'])
            print(f"\nHomepage Breakdown: {len(homepage_data)} items")
            print("-"*80)
            
            print("\nFirst 5 items (showing all fields):")
            for i, item in enumerate(homepage_data[:5], 1):
                print(f"\n{i}. {item}")
            
            # Check if all values are 0
            all_zeros = True
            for item in homepage_data:
                if (item.get('impressions', 0) != 0 or 
                    item.get('visits', 0) != 0):
                    all_zeros = False
                    break
            
            if all_zeros:
                print("\n" + "!"*80)
                print("WARNING: ALL numeric values are 0!")
                print("!"*80)
            else:
                print("\n" + "="*80)
                print("Some non-zero values found - data extraction working")
                print("="*80)
        else:
            print("\nHomepage Breakdown: NULL")
        
        # Inspect all_source_breakdown for comparison
        if row['all_source_breakdown']:
            source_data = json.loads(row['all_source_breakdown'])
            print(f"\n\nAll Source Breakdown: {len(source_data)} items")
            print("-"*80)
            print("\nFirst 3 items:")
            for i, item in enumerate(source_data[:3], 1):
                print(f"\n{i}. {item['page_feature']}")
                print(f"   Impressions: {item.get('impressions', 0)}")
                print(f"   Visits: {item.get('visits', 0)}")
    else:
        print("No data found in database")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()







