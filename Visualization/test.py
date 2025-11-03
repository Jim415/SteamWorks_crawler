#!/usr/bin/env python3
"""
Simple Test Script for SteamWorks Visualization System
Run this from the Visualization directory to test all components.
"""

import sys
import os
from datetime import datetime

# Add lib directory to path
lib_path = os.path.join(os.path.dirname(__file__), 'lib')
sys.path.insert(0, lib_path)

def main():
    print("=" * 60)
    print("SteamWorks Visualization System - Test")
    print("=" * 60)
    print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test 1: Database Connection
    print("1. Testing database connection...")
    try:
        from db_connector import test_connection
        if test_connection():
            print("   ✅ Database connection: SUCCESS")
        else:
            print("   ❌ Database connection: FAILED")
            return False
    except Exception as e:
        print(f"   ❌ Database connection: ERROR - {str(e)}")
        return False
    
    # Test 2: Data Loading
    print("\n2. Testing data loading...")
    try:
        from data_loader import get_latest_stat_date, get_dau_new_users_trend, get_revenue_trend
        
        # Test latest date
        latest_date = get_latest_stat_date()
        print(f"   ✅ Latest stat_date: {latest_date}")
        
        # Test DAU data
        df_dau = get_dau_new_users_trend()
        print(f"   ✅ DAU data: {len(df_dau)} rows")
        if not df_dau.empty:
            games = df_dau['game_name'].unique()
            print(f"   ✅ Games found: {list(games)}")
        
        # Test revenue data
        df_revenue = get_revenue_trend()
        print(f"   ✅ Revenue data: {len(df_revenue)} rows")
        
    except Exception as e:
        print(f"   ❌ Data loading: ERROR - {str(e)}")
        return False
    
    # Test 3: Chart Creation
    print("\n3. Testing chart creation...")
    try:
        from chart_builder import create_dau_new_users_chart, create_revenue_chart
        
        if not df_dau.empty:
            fig_dau = create_dau_new_users_chart(df_dau)
            print("   ✅ DAU chart: CREATED")
        
        if not df_revenue.empty:
            fig_revenue = create_revenue_chart(df_revenue)
            print("   ✅ Revenue chart: CREATED")
        
    except Exception as e:
        print(f"   ❌ Chart creation: ERROR - {str(e)}")
        return False
    
    # Test 4: Alert System
    print("\n4. Testing alert system...")
    try:
        from alert_engine import check_data_freshness
        
        alert_result = check_data_freshness()
        print(f"   ✅ Alert check: COMPLETED")
        print(f"   ✅ Alert triggered: {alert_result['alert_triggered']}")
        print(f"   ✅ Message: {alert_result['message']}")
        
    except Exception as e:
        print(f"   ❌ Alert system: ERROR - {str(e)}")
        return False
    
    # Success!
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("\nYour visualization system is ready!")
    print("\nNext steps:")
    print("1. Run: jupyter lab")
    print("2. Open: dashboard.ipynb")
    print("3. Run all cells to see your charts!")
    print("\nCharts will be exported to: exports/charts/")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n❌ Some tests failed. Check the errors above.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {str(e)}")
        sys.exit(1)





