import mysql.connector
from mysql.connector import Error

def check_database():
    """Check what data is in the database"""
    
    # Database configuration
    config = {
        'host': 'localhost',
        'port': 3306,
        'database': 'steamworks_crawler',
        'user': 'root',
        'password': 'Zh1149191843!'
    }
    
    connection = None
    cursor = None
    
    try:
        print("=== Database Content Check ===")
        
        # Connect to database
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Check total records
        cursor.execute("SELECT COUNT(*) FROM terminull_brigade_swcrawler")
        count = cursor.fetchone()[0]
        print(f"Total records in table: {count}")
        
        if count > 0:
            # Show all records
            cursor.execute("SELECT * FROM terminull_brigade_swcrawler ORDER BY date DESC")
            records = cursor.fetchall()
            
            print(f"\nLatest {min(5, len(records))} records:")
            for i, record in enumerate(records[:5]):
                print(f"\nRecord {i+1}:")
                print(f"  ID: {record[0]}")
                print(f"  Date: {record[1]}")
                print(f"  Unique Users Lifetime: {record[4]}")
                print(f"  Median Playtime: {record[8]}")
                print(f"  Total Revenue: {record[11]}")
                print(f"  Playtime Breakdown: {record[9][:100] if record[9] else 'None'}...")
        else:
            print("No records found in the table")
        
    except Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    check_database() 