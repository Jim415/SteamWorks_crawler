#!/usr/bin/env python3
"""
Script to check and analyze the historical marketing data in the database
"""

import mysql.connector
from mysql.connector import Error
import json
from datetime import date, timedelta

def connect_to_database():
    """Connect to the database"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            port=3306,
            database='steamworks_crawler',
            user='root',
            password='Zh1149191843!'
        )
        return connection
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None

def check_historical_data():
    """Check the historical data in delta_force_daily_marketing table"""
    connection = connect_to_database()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        
        # Get all records from delta_force_daily_marketing table
        query = """
        SELECT stat_date, 
               total_impressions, 
               total_visits,
               homepage_breakdown
        FROM delta_force_daily_marketing 
        ORDER BY stat_date
        """
        
        cursor.execute(query)
        records = cursor.fetchall()
        
        print(f"Found {len(records)} records in delta_force_daily_marketing table")
        print("=" * 80)
        
        # Analyze each record
        for i, record in enumerate(records):
            stat_date, total_impressions, total_visits, homepage_breakdown_json = record
            
            print(f"\nRecord {i+1}: {stat_date}")
            print(f"  Total Impressions: {total_impressions:,}")
            print(f"  Total Visits: {total_visits:,}")
            
            # Parse homepage_breakdown JSON
            if homepage_breakdown_json:
                try:
                    homepage_breakdown = json.loads(homepage_breakdown_json)
                    print(f"  Homepage Breakdown: {len(homepage_breakdown)} entries")
                    
                    # Show first few entries
                    for j, entry in enumerate(homepage_breakdown[:3]):
                        page_feature = entry.get('page_feature', 'Unknown')
                        impressions = entry.get('impressions', 0)
                        visits = entry.get('visits', 0)
                        print(f"    {j+1}. {page_feature}: {impressions:,} impressions, {visits:,} visits")
                    
                    if len(homepage_breakdown) > 3:
                        print(f"    ... and {len(homepage_breakdown) - 3} more entries")
                        
                except json.JSONDecodeError as e:
                    print(f"  ERROR: Invalid JSON in homepage_breakdown: {e}")
                    print(f"  Raw data: {homepage_breakdown_json[:200]}...")
            else:
                print("  Homepage Breakdown: NULL or empty")
        
        # Compare specific dates (Dec 5th vs Dec 13th)
        print("\n" + "=" * 80)
        print("COMPARING DEC 5TH vs DEC 13TH")
        print("=" * 80)
        
        dec_5_query = """
        SELECT stat_date, homepage_breakdown
        FROM delta_force_daily_marketing 
        WHERE stat_date = '2024-12-05'
        """
        
        dec_13_query = """
        SELECT stat_date, homepage_breakdown
        FROM delta_force_daily_marketing 
        WHERE stat_date = '2024-12-13'
        """
        
        cursor.execute(dec_5_query)
        dec_5_record = cursor.fetchone()
        
        cursor.execute(dec_13_query)
        dec_13_record = cursor.fetchone()
        
        if dec_5_record and dec_13_record:
            print(f"\nDec 5th ({dec_5_record[0]}):")
            if dec_5_record[1]:
                try:
                    dec_5_data = json.loads(dec_5_record[1])
                    print(f"  Homepage entries: {len(dec_5_data)}")
                    for entry in dec_5_data:
                        print(f"    - {entry.get('page_feature', 'Unknown')}: {entry.get('impressions', 0):,} impressions")
                except json.JSONDecodeError:
                    print("  ERROR: Invalid JSON")
            else:
                print("  Homepage breakdown: NULL")
            
            print(f"\nDec 13th ({dec_13_record[0]}):")
            if dec_13_record[1]:
                try:
                    dec_13_data = json.loads(dec_13_record[1])
                    print(f"  Homepage entries: {len(dec_13_data)}")
                    for entry in dec_13_data:
                        print(f"    - {entry.get('page_feature', 'Unknown')}: {entry.get('impressions', 0):,} impressions")
                except json.JSONDecodeError:
                    print("  ERROR: Invalid JSON")
            else:
                print("  Homepage breakdown: NULL")
        
        # Check for any records with NULL or empty homepage_breakdown
        print("\n" + "=" * 80)
        print("CHECKING FOR NULL/EMPTY HOMEPAGE_BREAKDOWN")
        print("=" * 80)
        
        null_query = """
        SELECT stat_date, total_impressions, total_visits
        FROM delta_force_daily_marketing 
        WHERE homepage_breakdown IS NULL OR homepage_breakdown = ''
        ORDER BY stat_date
        """
        
        cursor.execute(null_query)
        null_records = cursor.fetchall()
        
        if null_records:
            print(f"Found {len(null_records)} records with NULL/empty homepage_breakdown:")
            for record in null_records:
                print(f"  {record[0]}: {record[1]:,} impressions, {record[2]:,} visits")
        else:
            print("No records found with NULL/empty homepage_breakdown")
        
        # Check for records with very few homepage entries (potential issue)
        print("\n" + "=" * 80)
        print("CHECKING FOR RECORDS WITH FEW HOMEPAGE ENTRIES")
        print("=" * 80)
        
        cursor.execute("SELECT stat_date, homepage_breakdown FROM delta_force_daily_marketing ORDER BY stat_date")
        all_records = cursor.fetchall()
        
        for record in all_records:
            stat_date, homepage_breakdown_json = record
            if homepage_breakdown_json:
                try:
                    homepage_breakdown = json.loads(homepage_breakdown_json)
                    if len(homepage_breakdown) < 5:  # Less than 5 entries might indicate an issue
                        print(f"  {stat_date}: Only {len(homepage_breakdown)} homepage entries")
                        for entry in homepage_breakdown:
                            print(f"    - {entry.get('page_feature', 'Unknown')}")
                except json.JSONDecodeError:
                    print(f"  {stat_date}: Invalid JSON")
        
    except Error as e:
        print(f"Database error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    check_historical_data()

