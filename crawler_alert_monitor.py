#!/usr/bin/env python3
"""
SteamWorks Crawler Alert Monitor
Checks database and log files for crawler execution status and sends WeCom alerts.
Runs at 4:35 PM Beijing Time (5 minutes after crawler start at 4:30 PM).
"""

import mysql.connector
from mysql.connector import Error
import json
import logging
import os
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None

# Setup logging
log_file = os.path.join(os.path.dirname(__file__), 'crawler_alert_monitor.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Hardcoded games list (from steamworks_crawler.py)
EXPECTED_GAMES = [
    (2507950, 'Delta Force'),
    (2073620, 'Arena Breakout: Infinite'),
    (3478050, 'Road to Empress'),
    (3104410, 'Terminull Brigade'),
]

# Database configuration (same as crawler)
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'steamworks_crawler',
    'user': 'root',
    'password': 'Zh1149191843!'
}

# Configuration file path
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'alert_config.json')

# Log file path
CRAWLER_LOG_FILE = os.path.join(os.path.dirname(__file__), 'steamworks_crawler.log')


def load_webhook_config():
    """Load WeCom webhook URL from config file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('wecom_webhook_url', '')
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            return ''
    else:
        logger.warning(f"Config file not found: {CONFIG_FILE}")
        logger.info("Please create alert_config.json with your WeCom webhook URL")
        return ''


def save_webhook_config(webhook_url):
    """Save WeCom webhook URL to config file"""
    config = {
        'wecom_webhook_url': webhook_url
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Webhook URL saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save config file: {e}")
        return False


def calculate_expected_stat_date():
    """
    Calculate expected stat_date using same logic as crawler.
    Returns: date object (Pacific Time yesterday)
    """
    if ZoneInfo:
        now_pt = datetime.now(ZoneInfo('America/Los_Angeles'))
        expected_date = (now_pt - timedelta(days=1)).date()
        logger.info(f"Pacific time now: {now_pt}, expected stat_date: {expected_date}")
    else:
        # Fallback to system local time minus one day
        expected_date = (datetime.now() - timedelta(days=1)).date()
        logger.warning("ZoneInfo not available, using system local time")
        logger.info(f"System time, expected stat_date: {expected_date}")
    return expected_date


def check_database(expected_stat_date):
    """
    Check database for expected rows and NULL critical columns.
    Returns: dict with status for each game
    {
        'games_status': [
            {'app_id': 2507950, 'game_name': 'Delta Force', 'status': 'ok'/'missing'/'wrong_date'/'incomplete', 'stat_date': date}
        ],
        'missing_games': [...],
        'wrong_date_games': [...],
        'games_with_null_unique_player': [...]
    }
    """
    results = {
        'games_status': [],
        'missing_games': [],
        'wrong_date_games': [],
        'games_with_null_unique_player': []
    }
    
    connection = None
    cursor = None
    
    try:
        logger.info("Connecting to database...")
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        
        for app_id, game_name in EXPECTED_GAMES:
            # Query for this game with expected stat_date, including unique_player
            query = """
            SELECT steam_app_id, game_name, stat_date, dau, unique_player
            FROM game_daily_metrics
            WHERE stat_date = %s AND steam_app_id = %s
            """
            cursor.execute(query, (expected_stat_date, app_id))
            row = cursor.fetchone()
            
            if row is None:
                # Missing row
                status = 'missing'
                results['missing_games'].append({
                    'app_id': app_id,
                    'game_name': game_name
                })
            elif row['stat_date'] != expected_stat_date:
                # Wrong date (should not happen, but check anyway)
                status = 'wrong_date'
                results['wrong_date_games'].append({
                    'app_id': app_id,
                    'game_name': game_name,
                    'found_date': row['stat_date'],
                    'expected_date': expected_stat_date
                })
            elif row.get('unique_player') is None:
                # Row exists but unique_player is NULL (incomplete data)
                status = 'incomplete'
                results['games_with_null_unique_player'].append({
                    'app_id': app_id,
                    'game_name': game_name
                })
            else:
                # OK
                status = 'ok'
            
            results['games_status'].append({
                'app_id': app_id,
                'game_name': game_name,
                'status': status,
                'stat_date': row['stat_date'] if row else None
            })
            
            logger.info(f"Game {game_name} ({app_id}): {status}")
        
        logger.info(f"Database check completed. Missing: {len(results['missing_games'])}, Wrong date: {len(results['wrong_date_games'])}, NULL unique_player: {len(results['games_with_null_unique_player'])}")
        return results
        
    except Error as e:
        logger.error(f"Database error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error checking database: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def check_log_file(minutes_back=10):
    """
    Check crawler log file for errors in the last N minutes.
    Returns: list of error messages
    """
    errors = []
    
    if not os.path.exists(CRAWLER_LOG_FILE):
        logger.warning(f"Log file not found: {CRAWLER_LOG_FILE}")
        return errors
    
    try:
        # Calculate time threshold
        now = datetime.now()
        threshold = now - timedelta(minutes=minutes_back)
        
        logger.info(f"Checking log file for errors since {threshold}")
        
        with open(CRAWLER_LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Read from end (most recent first) to find recent errors
        for line in reversed(lines):
            if not line.strip():
                continue
            
            # Try to parse timestamp (format: "2025-12-01 16:32:15,123 - ...")
            try:
                # Extract timestamp part
                if ' - ' in line:
                    timestamp_str = line.split(' - ')[0].strip()
                    # Remove milliseconds if present
                    if ',' in timestamp_str:
                        timestamp_str = timestamp_str.split(',')[0]
                    
                    log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    if log_time < threshold:
                        # We've gone past our time window, stop reading
                        break
                else:
                    # No timestamp found, skip
                    continue
            except (ValueError, IndexError):
                # Can't parse timestamp, skip
                continue
            
            # Check for error and warning patterns
            line_lower = line.lower()
            if any(pattern in line_lower for pattern in [
                'error',
                'failed to extract',
                'database error',
                'crawler execution failed',
                'manual login required',
                'login required',
                'access denied',
                # Add WARNING level patterns for Issue 2 detection
                'timeout navigating to default game page',
                'default game page extraction failed',
                'failed to get lifetime unique users',
                'failed to get lifetime total units',
                'failed to get wishlists',
                'failed to get lifetime steam revenue'
            ]):
                # Extract just the message part (after timestamp)
                if ' - ' in line:
                    message = ' - '.join(line.split(' - ')[1:]).strip()
                    errors.append({
                        'timestamp': timestamp_str,
                        'message': message
                    })
        
        # Reverse to get chronological order
        errors.reverse()
        
        logger.info(f"Found {len(errors)} error(s) in log file")
        return errors
        
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return errors


def send_wecom_alert(webhook_url, message):
    """
    Send alert message to WeCom webhook.
    Returns: True if successful, False otherwise
    """
    if not webhook_url:
        logger.error("Webhook URL not configured")
        return False
    
    try:
        import urllib.request
        import urllib.parse
        import urllib.error
        
        # Prepare message payload
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        
        data = json.dumps(payload).encode('utf-8')
        logger.debug(f"Sending webhook request to: {webhook_url[:50]}...")
        logger.debug(f"Message length: {len(message)} characters")
        
        req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json; charset=utf-8'})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                logger.debug(f"WeCom response: {response_data}")
                result = json.loads(response_data)
                
                errcode = result.get('errcode', -1)
                errmsg = result.get('errmsg', 'No error message')
                
                if errcode == 0:
                    logger.info("Alert sent successfully to WeCom (errcode=0)")
                    return True
                else:
                    logger.error(f"WeCom API returned error - errcode: {errcode}, errmsg: {errmsg}")
                    logger.error(f"Full response: {response_data}")
                    return False
                    
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error when sending to WeCom: {e.code} - {e.reason}")
            try:
                error_body = e.read().decode('utf-8')
                logger.error(f"Error response body: {error_body}")
            except:
                pass
            return False
        except urllib.error.URLError as e:
            logger.error(f"URL error when sending to WeCom: {e.reason}")
            return False
                
    except Exception as e:
        logger.error(f"Failed to send WeCom alert: {e}", exc_info=True)
        return False


def format_success_alert():
    """Format alert message for successful run"""
    now_beijing = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    message = f"""✅ SteamWorks Crawler Alert - Success

**Date**: {now_beijing} (Beijing Time)

**Status**: All crawler runs completed successfully

All 4 games have data in database with correct stat_date."""
    
    return message


def format_failure_alert(expected_stat_date, db_results, log_errors):
    """Format alert message for failed run"""
    now_beijing = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    message = f"""🚨 SteamWorks Crawler Alert - Failure

**Date**: {now_beijing} (Beijing Time)
**Expected stat_date**: {expected_stat_date} (PST)

**Game Status**:"""
    
    # Add status for each game
    for game_status in db_results['games_status']:
        app_id = game_status['app_id']
        game_name = game_status['game_name']
        status = game_status['status']
        
        if status == 'ok':
            message += f"\n✓ {game_name} ({app_id}) - OK"
        elif status == 'missing':
            message += f"\n✗ {game_name} ({app_id}) - MISSING"
        elif status == 'wrong_date':
            found_date = game_status.get('stat_date')
            message += f"\n⚠ {game_name} ({app_id}) - WRONG DATE (found: {found_date})"
        elif status == 'incomplete':
            message += f"\n⚠ {game_name} ({app_id}) - INCOMPLETE (unique_player is NULL)"
    
    # Add issue summary
    missing_count = len(db_results['missing_games'])
    wrong_date_count = len(db_results['wrong_date_games'])
    null_unique_player_count = len(db_results.get('games_with_null_unique_player', []))
    
    if missing_count > 0 or wrong_date_count > 0 or null_unique_player_count > 0:
        message += f"\n\n**Issue Summary**:"
        if missing_count > 0:
            missing_names = [g['game_name'] for g in db_results['missing_games']]
            message += f"\n- Missing data for {missing_count} game(s): {', '.join(missing_names)}"
        if wrong_date_count > 0:
            wrong_names = [g['game_name'] for g in db_results['wrong_date_games']]
            message += f"\n- Wrong date for {wrong_date_count} game(s): {', '.join(wrong_names)}"
        if null_unique_player_count > 0:
            null_names = [g['game_name'] for g in db_results['games_with_null_unique_player']]
            message += f"\n- Incomplete data (unique_player is NULL) for {null_unique_player_count} game(s): {', '.join(null_names)}"
    
    # Add log errors if any
    if log_errors:
        message += f"\n\n**Log Errors**:"
        for error in log_errors[-5:]:  # Show last 5 errors
            message += f"\n- [{error['timestamp']}] {error['message']}"
    
    return message


def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("SteamWorks Crawler Alert Monitor - Starting")
    logger.info("=" * 60)
    
    # Load webhook URL
    webhook_url = load_webhook_config()
    
    # If webhook URL is not configured, prompt user (only if interactive)
    if not webhook_url:
        logger.warning("\n" + "=" * 60)
        logger.warning("WeCom Webhook URL not configured!")
        logger.warning("=" * 60)
        logger.warning("Please provide your WeCom webhook URL.")
        logger.warning("See WECOM_WEBHOOK_SETUP.md for instructions on how to get one.")
        logger.warning("")
        
        # Try to get user input (only if running interactively)
        try:
            user_input = input("Enter WeCom webhook URL (or press Enter to skip sending alerts): ").strip()
            
            if user_input:
                if save_webhook_config(user_input):
                    webhook_url = user_input
                    logger.info("Webhook URL saved successfully!")
                else:
                    logger.error("Failed to save webhook URL")
            else:
                logger.warning("No webhook URL provided. Alerts will not be sent.")
                logger.warning("You can configure it later by editing alert_config.json")
        except (EOFError, KeyboardInterrupt):
            # Running non-interactively (e.g., from Task Scheduler)
            logger.warning("Running in non-interactive mode. Cannot prompt for webhook URL.")
            logger.warning("Please create alert_config.json manually with your webhook URL.")
            logger.warning("Alerts will not be sent until webhook URL is configured.")
    
    # Calculate expected stat_date
    expected_stat_date = calculate_expected_stat_date()
    logger.info(f"Checking for expected stat_date: {expected_stat_date}")
    
    # Check database
    logger.info("Checking database...")
    db_results = check_database(expected_stat_date)
    
    if db_results is None:
        logger.error("Failed to check database. Cannot proceed with alert.")
        return 1
    
    # Check log file
    logger.info("Checking log file...")
    log_errors = check_log_file(minutes_back=10)
    
    # Determine if there are issues
    has_issues = (
        len(db_results['missing_games']) > 0 or
        len(db_results['wrong_date_games']) > 0 or
        len(db_results.get('games_with_null_unique_player', [])) > 0 or
        len(log_errors) > 0
    )
    
    # Format and send alert
    if has_issues:
        logger.warning("Issues detected! Sending failure alert...")
        alert_message = format_failure_alert(expected_stat_date, db_results, log_errors)
    else:
        logger.info("All checks passed! Sending success alert...")
        alert_message = format_success_alert()
    
    # Log alert message (safe for any encoding - remove emojis for logging)
    logger.info("Alert message prepared:")
    # Remove emojis from log message to avoid encoding issues
    log_safe_message = alert_message.replace('✅', '[SUCCESS]').replace('🚨', '[FAILURE]').replace('✓', '[OK]').replace('✗', '[MISSING]').replace('⚠', '[WARNING]')
    logger.info(log_safe_message)
    
    # Print alert message to console (safe for Windows GBK encoding)
    try:
        # Try to print with UTF-8 encoding if possible
        import sys
        if sys.stdout.encoding and 'utf' in sys.stdout.encoding.lower():
            print("\n" + "=" * 60)
            print("ALERT MESSAGE:")
            print("=" * 60)
            print(alert_message)
            print("=" * 60 + "\n")
        else:
            # For GBK/ASCII consoles, print without emojis
            safe_message = alert_message.replace('✅', '[SUCCESS]').replace('🚨', '[FAILURE]').replace('✓', '[OK]').replace('✗', '[MISSING]').replace('⚠', '[WARNING]')
            print("\n" + "=" * 60)
            print("ALERT MESSAGE:")
            print("=" * 60)
            print(safe_message)
            print("=" * 60 + "\n")
    except (UnicodeEncodeError, UnicodeError) as e:
        # If printing still fails, just log it and continue
        logger.warning(f"Could not print alert message to console (encoding issue): {e}")
        logger.info("Alert message will still be sent via WeCom")
    
    # Send alert via WeCom if configured (this is the critical part - must not fail)
    if webhook_url:
        try:
            success = send_wecom_alert(webhook_url, alert_message)
            if success:
                logger.info("Alert sent successfully to WeCom")
                return 0 if not has_issues else 1
            else:
                logger.error("Failed to send alert to WeCom")
                return 2
        except Exception as e:
            logger.error(f"Exception while sending alert to WeCom: {e}", exc_info=True)
            return 2
    else:
        logger.warning("Alert not sent (no webhook URL configured)")
        return 0 if not has_issues else 1


if __name__ == "__main__":
    sys.exit(main())
