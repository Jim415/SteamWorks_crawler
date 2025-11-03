"""
Dashboard Refresh Script
Executes the Jupyter dashboard notebook using Papermill for automated daily refresh.
Designed to be run by Windows Task Scheduler daily after the crawler completes.
"""

import sys
import os
import logging
from datetime import datetime
import papermill as pm

# Setup logging
log_file = os.path.join(os.path.dirname(__file__), 'refresh_dashboard.log')
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
    print("SteamWorks Dashboard - Automated Refresh")
    print("=" * 60)
    print(f"Execution time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_notebook = os.path.join(script_dir, 'dashboard.ipynb')
    
    # Create timestamped output in exports directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(script_dir, 'exports')
    os.makedirs(output_dir, exist_ok=True)
    output_notebook = os.path.join(output_dir, f'dashboard_{timestamp}.ipynb')
    
    # Also update the "latest" version
    latest_notebook = os.path.join(output_dir, 'dashboard_latest.ipynb')
    
    try:
        logger.info(f"Executing notebook: {input_notebook}")
        print(f"Input notebook: {input_notebook}")
        print(f"Output notebook: {output_notebook}")
        print()
        
        # Execute notebook with papermill
        pm.execute_notebook(
            input_notebook,
            output_notebook,
            parameters={
                'auto_refresh': True,
                'refresh_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            kernel_name='python3',
            progress_bar=True
        )
        
        # Copy to "latest" version
        import shutil
        shutil.copy2(output_notebook, latest_notebook)
        
        logger.info("Dashboard refresh completed successfully")
        print()
        print("✓ Dashboard refresh completed successfully!")
        print(f"  Output saved to: {output_notebook}")
        print(f"  Latest version: {latest_notebook}")
        print()
        print("=" * 60)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Dashboard refresh failed: {str(e)}", exc_info=True)
        print(f"\n✗ ERROR: Dashboard refresh failed - {str(e)}")
        print("See refresh_dashboard.log for details")
        sys.exit(1)

if __name__ == "__main__":
    main()

