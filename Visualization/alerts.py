"""
Standalone Alert Execution Script
Runs all alert checks and sends email notifications if alerts are triggered.
Designed to be run by Windows Task Scheduler daily.
"""

import sys
import os
import logging
from datetime import datetime

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from alert_engine import run_all_alerts

# Setup logging
log_file = os.path.join(os.path.dirname(__file__), 'alerts.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main execution function"""
    print("=" * 60)
    print("SteamWorks Dashboard - Alert System")
    print("=" * 60)
    print(f"Execution time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Run all alert checks
        logger.info("Starting alert checks...")
        summary = run_all_alerts()
        
        # Display results
        print(f"\nAlert Check Summary:")
        print(f"  Total checks performed: {summary['total_checks']}")
        print(f"  Alerts triggered: {summary['triggered_alerts']}")
        print(f"  Email sent: {'Yes' if summary['email_sent'] else 'No'}")
        print()
        
        # Display individual alert details
        if summary['triggered_alerts'] > 0:
            print("Alert Details:")
            for i, alert in enumerate(summary['alerts'], 1):
                if alert.get('alert_triggered', False):
                    print(f"\n  Alert {i}:")
                    print(f"    Severity: {alert.get('severity', 'unknown').upper()}")
                    print(f"    Message: {alert.get('message', 'No message')}")
                    if alert.get('details'):
                        print(f"    Details: {alert['details']}")
        else:
            print("✓ No alerts triggered - all systems normal")
        
        print()
        print("=" * 60)
        logger.info("Alert check completed successfully")
        
        # Exit with appropriate code
        sys.exit(0 if summary['triggered_alerts'] == 0 else 1)
        
    except Exception as e:
        logger.error(f"Alert check failed: {str(e)}", exc_info=True)
        print(f"\n✗ ERROR: Alert check failed - {str(e)}")
        print("See alerts.log for details")
        sys.exit(2)

if __name__ == "__main__":
    main()

