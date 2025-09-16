#!/bin/bash

# SteamWorks Crawler - Daily Execution Script
# This script activates the virtual environment and runs the crawler

# Set PATH for cron environment
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "=== SteamWorks Crawler - Daily Run ==="
echo "Date: $(date)"
echo ""

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Run the crawler
echo "Starting SteamWorks crawler..."
python3 steamworks_crawler.py

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