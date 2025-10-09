#!/usr/bin/env python3
"""
Configuration script for running historical marketing data crawler
"""

from datetime import date, timedelta
from steamworks_historical_marketing_crawler import SteamworksHistoricalMarketingCrawler

def main():
    """Main function to configure and run historical crawler"""
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'database': 'steamworks_crawler',
        'user': 'root',
        'password': 'Zh1149191843!'
    }
    
    # Fixed configuration for Delta Force only
    steam_app_id = 2507950
    game_name = 'Delta Force'
    
    print("=== SteamWorks Historical Marketing Data Crawler ===")
    print(f"Game: {game_name} (ID: {steam_app_id})")
    print("This will fetch 30 days of marketing data starting from your input date.")
    print()
    
    # Get start date from user
    while True:
        try:
            start_date_str = input("Enter start date (YYYYMMDD format): ").strip()
            if len(start_date_str) != 8:
                print("Error: Date must be in YYYYMMDD format (8 digits)")
                continue
            
            year = int(start_date_str[:4])
            month = int(start_date_str[4:6])
            day = int(start_date_str[6:8])
            
            start_date = date(year, month, day)
            break
            
        except ValueError as e:
            print(f"Error: Invalid date format. Please use YYYYMMDD format. ({e})")
            continue
    
    # Calculate end date (30 days including start date)
    end_date = start_date + timedelta(days=29)
    
    # Display configuration
    print(f"\n=== Configuration ===")
    print(f"Game: {game_name} (ID: {steam_app_id})")
    print(f"Start date: {start_date}")
    print(f"End date: {end_date}")
    print(f"Total days: 30")
    print(f"Data will be stored in: steamworks_crawler.delta_force_daily_marketing table only")
    
    # Confirm before proceeding
    confirm = input("\nDo you want to proceed? (y/N): ")
    if confirm.lower() != 'y':
        print("Cancelled by user.")
        return
    
    # Run the crawler
    print(f"\nStarting historical crawler...")
    crawler = SteamworksHistoricalMarketingCrawler(
        db_config, 
        steam_app_id=steam_app_id, 
        game_name=game_name,
        start_date=start_date,
        end_date=end_date
    )
    
    success, result = crawler.run_historical_crawler()
    
    if success:
        print(f"\n✅ Historical marketing crawler completed successfully!")
        print(f"Result: {result}")
    else:
        print(f"\n❌ Historical marketing crawler failed: {result}")

if __name__ == "__main__":
    main()
