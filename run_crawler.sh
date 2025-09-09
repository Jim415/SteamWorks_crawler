#!/bin/bash

# SteamWorks Crawler - Daily Execution Script
# This script activates the virtual environment and runs the crawler

echo "=== SteamWorks Crawler - Daily Run ==="
echo "Date: $(date)"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Run the crawler
echo "Starting SteamWorks crawler..."
python steamworks_crawler.py

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Crawler completed successfully!"
    echo "Check steamworks_crawler.log for details"
else
    echo ""
    echo "❌ Crawler failed!"
    echo "Check steamworks_crawler.log for error details"
    exit 1
fi 