#!/usr/bin/env python3
"""
Chart Export Script
Standalone script to export dashboard charts to HTML and PNG formats.
Run this manually when you need to share charts with teammates.
"""

import sys
import os
from datetime import datetime
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# Add lib directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.insert(0, lib_path)

# Import visualization modules
from lib import (
    get_dau_new_users_trend,
    get_revenue_trend,
    create_dau_new_users_chart,
    create_revenue_chart
)

def main():
    print("=" * 60)
    print("SteamWorks Chart Export Tool")
    print("=" * 60)
    print(f"Export started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Set up export directory
    export_dir = os.path.join(current_dir, 'exports', 'charts')
    os.makedirs(export_dir, exist_ok=True)
    
    # Get date range (default: from Oct 1, 2025 to today)
    start_date = '2025-10-01'
    end_date = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%Y%m%d')
    
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Export Timestamp: {timestamp}")
    print()
    
    # Load data
    print("Loading data from database...")
    try:
        df_dau = get_dau_new_users_trend(start_date, end_date)
        df_revenue = get_revenue_trend(start_date, end_date)
        print(f"✓ Loaded {len(df_dau)} rows of DAU/New Users data")
        print(f"✓ Loaded {len(df_revenue)} rows of Revenue data")
    except Exception as e:
        print(f"❌ Error loading data: {str(e)}")
        return False
    
    # Create charts
    print("\nCreating charts...")
    try:
        fig_dau = create_dau_new_users_chart(df_dau, title="DAU & New Users Trend - All Games")
        fig_revenue = create_revenue_chart(df_revenue, title="Daily Revenue Trend - Portfolio View")
        print("✓ Charts created successfully")
    except Exception as e:
        print(f"❌ Error creating charts: {str(e)}")
        return False
    
    # Export charts
    print("\nExporting charts...")
    
    # Export DAU chart
    dau_html_path = os.path.join(export_dir, f'dau_new_users_{timestamp}.html')
    dau_png_path = os.path.join(export_dir, f'dau_new_users_{timestamp}.png')
    
    try:
        fig_dau.write_html(dau_html_path)
        print(f"✓ DAU chart exported to HTML: {os.path.basename(dau_html_path)}")
    except Exception as e:
        print(f"❌ HTML export failed: {e}")
    
    try:
        fig_dau.write_image(dau_png_path, width=1920, height=1080)
        print(f"✓ DAU chart exported to PNG: {os.path.basename(dau_png_path)}")
    except Exception as e:
        print(f"⚠ PNG export failed (install kaleido): {e}")
    
    # Export Revenue chart
    revenue_html_path = os.path.join(export_dir, f'revenue_{timestamp}.html')
    revenue_png_path = os.path.join(export_dir, f'revenue_{timestamp}.png')
    
    try:
        fig_revenue.write_html(revenue_html_path)
        print(f"✓ Revenue chart exported to HTML: {os.path.basename(revenue_html_path)}")
    except Exception as e:
        print(f"❌ HTML export failed: {e}")
    
    try:
        fig_revenue.write_image(revenue_png_path, width=1920, height=1080)
        print(f"✓ Revenue chart exported to PNG: {os.path.basename(revenue_png_path)}")
    except Exception as e:
        print(f"⚠ PNG export failed (install kaleido): {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 EXPORT COMPLETE!")
    print("=" * 60)
    print(f"\nFiles exported to: {export_dir}")
    print("\nExported files:")
    
    exported_files = []
    for filename in os.listdir(export_dir):
        if filename.endswith(('.html', '.png')) and timestamp in filename:
            exported_files.append(filename)
    
    if exported_files:
        for file in sorted(exported_files):
            print(f"  📄 {file}")
    else:
        print("  No files found with today's timestamp")
    
    print(f"\n💡 Usage:")
    print(f"  • HTML files: Open in browser for interactive viewing")
    print(f"  • PNG files: Use in PowerPoint presentations")
    print(f"  • Share with teammates as needed")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n❌ Export failed. Check the errors above.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Export failed with exception: {str(e)}")
        sys.exit(1)





