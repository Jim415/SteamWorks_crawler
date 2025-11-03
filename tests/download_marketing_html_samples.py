"""
SteamWorks Marketing HTML Downloader
Downloads HTML snapshots of the marketing traffic stats page for multiple dates
Useful for analyzing HTML structure changes over time
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import quote

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download_marketing_html.log'),
        logging.StreamHandler()
    ]
)

class MarketingHTMLDownloader:
    def __init__(self, steam_app_id, game_name, start_date, num_days=30):
        """
        Initialize the HTML downloader
        
        Args:
            steam_app_id: Steam app ID (e.g., 2507950 for Delta Force)
            game_name: Game name for logging
            start_date: Starting date (datetime.date object)
            num_days: Number of consecutive days to download (default: 30)
        """
        self.steam_app_id = steam_app_id
        self.game_name = game_name
        self.start_date = start_date
        self.num_days = num_days
        self.driver = None
        self.wait = None
        
        # Create output folder
        self.output_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sample marketing html files')
        os.makedirs(self.output_folder, exist_ok=True)
        logging.info(f"Output folder: {self.output_folder}")
    
    def setup_driver(self):
        """Setup Chrome with persistent user data directory to retain login"""
        chrome_options = Options()
        
        # Decide which Chrome profile to use (same logic as main crawler)
        use_system_profile = os.environ.get('STEAMWORKS_USE_SYSTEM_CHROME_PROFILE', '0') == '1'
        if use_system_profile:
            # Use existing system Chrome profile (already Steam Guard trusted)
            system_user_data = os.environ.get('STEAMWORKS_CHROME_USER_DATA_DIR')
            if not system_user_data:
                # Default Windows path
                system_user_data = os.path.expandvars(r"%LOCALAPPDATA%\\Google\\Chrome\\User Data")
            profile_name = os.environ.get('STEAMWORKS_CHROME_PROFILE_NAME', 'Default')

            # Optionally clone system profile to avoid 'in use' lock
            clone_flag = os.environ.get('STEAMWORKS_CLONE_SYSTEM_PROFILE', '1') == '1'
            force_reclone = os.environ.get('STEAMWORKS_FORCE_RECLONE', '0') == '1'
            if clone_flag:
                clone_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'chrome_profile_clone')
                src_profile_dir = os.path.join(system_user_data, profile_name)
                dst_profile_dir = os.path.join(clone_root, profile_name)
                try:
                    import shutil
                    if force_reclone and os.path.isdir(clone_root):
                        shutil.rmtree(clone_root, ignore_errors=True)
                    if not os.path.isdir(dst_profile_dir):
                        os.makedirs(clone_root, exist_ok=True)
                        # Copy 'Local State' if present
                        try:
                            shutil.copy2(os.path.join(system_user_data, 'Local State'), os.path.join(clone_root, 'Local State'))
                        except Exception:
                            pass
                        # Copy the profile folder while excluding caches/locks
                        shutil.copytree(
                            src_profile_dir,
                            dst_profile_dir,
                            ignore=shutil.ignore_patterns(
                                'Cache', 'Code Cache', 'GPUCache', 'ShaderCache', 'GrShaderCache', 'Media Cache',
                                'Crashpad', 'DawnCache', 'Network', 'Storage', 'Temp*', 'Singleton*', 'Lockfile'
                            )
                        )
                except Exception as e:
                    logging.warning(f"Profile clone failed, falling back to direct system profile: {str(e)}")
                    clone_flag = False

                if clone_flag:
                    chrome_options.add_argument(f"--user-data-dir={clone_root}")
                    chrome_options.add_argument(f"--profile-directory={profile_name}")
                else:
                    chrome_options.add_argument(f"--user-data-dir={system_user_data}")
                    chrome_options.add_argument(f"--profile-directory={profile_name}")
            else:
                chrome_options.add_argument(f"--user-data-dir={system_user_data}")
                chrome_options.add_argument(f"--profile-directory={profile_name}")
        else:
            # Use a persistent local profile inside repo to retain login across runs
            profile_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'chrome_profile')
            try:
                os.makedirs(profile_dir, exist_ok=True)
            except Exception:
                pass
            chrome_options.add_argument(f"--user-data-dir={profile_dir}")
            chrome_options.add_argument("--profile-directory=Default")

        # Stealth-ish flags to reduce automation detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        
        # Add options for stability
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)
        
        logging.info("Chrome WebDriver setup completed")
    
    def warmup_session(self):
        """Open SteamWorks home once to ensure domain session is active"""
        try:
            base_url = "https://partner.steampowered.com/"
            self.driver.get(base_url)
            time.sleep(2)
            current_url = self.driver.current_url
            logging.info(f"Warmup landed on: {current_url}")
        except Exception as e:
            logging.warning(f"Warmup failed: {str(e)}")
    
    def ensure_partner_context(self):
        """Switch to the correct partner account if needed"""
        try:
            target_name = os.environ.get('STEAMWORKS_TARGET_PARTNER_NAME', 'Proxima Beta Europe B.V.')
            target_id = os.environ.get('STEAMWORKS_TARGET_PARTNER_ID', '').strip()

            # Find the partner switcher select
            selects = self.driver.find_elements(By.XPATH, "//select[@name='runasPubid']")
            if not selects:
                logging.info("Partner switcher not found; proceeding with current context")
                return
            select_el = selects[0]

            # Determine current selected
            current_selected = None
            options = select_el.find_elements(By.XPATH, ".//option")
            for opt in options:
                if opt.get_attribute('selected') or opt.is_selected():
                    current_selected = {
                        'text': opt.text.strip(),
                        'value': (opt.get_attribute('value') or '').strip()
                    }
                    break

            if current_selected:
                if target_id and current_selected.get('value') == target_id:
                    logging.info(f"Already in target partner by id: {target_id}")
                    return
                if (not target_id) and current_selected.get('text') == target_name:
                    logging.info(f"Already in target partner by name: {target_name}")
                    return

            # Select target option
            target_opt = None
            if target_id:
                for opt in options:
                    if (opt.get_attribute('value') or '').strip() == target_id:
                        target_opt = opt
                        break
            if target_opt is None:
                for opt in options:
                    if opt.text.strip() == target_name:
                        target_opt = opt
                        break

            if target_opt is None:
                logging.warning("Target partner option not found; proceeding with current context")
                return

            target_opt.click()
            time.sleep(2)
            logging.info(f"Switched to partner context: {target_name}")
        except Exception as e:
            logging.warning(f"ensure_partner_context failed: {str(e)}")
    
    def navigate_to_marketing_page_base(self):
        """Navigate to the base marketing page to establish session (EXACT logic from steamworks_marketing_crawler.py)"""
        url = f"https://partner.steamgames.com/apps/navtrafficstats/{self.steam_app_id}"
        logging.info(f"Navigating to marketing page: {url}")
        self.driver.get(url)
        
        # Wait for page to load and any redirects
        time.sleep(5)
        
        # Check current URL to see if we were redirected
        current_url = self.driver.current_url
        logging.info(f"Current URL: {current_url}")
        
        # If we're on a redirect page (contains ?goto=), we need to follow the redirect
        if "?goto=" in current_url:
            logging.info("Detected redirect page, waiting for automatic redirect...")
            # Wait longer for the redirect to complete
            time.sleep(10)
            current_url = self.driver.current_url
            logging.info(f"URL after redirect wait: {current_url}")
            
            # If still on redirect page, try clicking the redirect link
            if "?goto=" in current_url:
                logging.info("Still on redirect page, attempting to follow redirect...")
                try:
                    # Look for redirect links or buttons
                    redirect_selectors = [
                        "//a[contains(@href, 'navtrafficstats')]",
                        "//a[contains(text(), 'Continue')]",
                        "//a[contains(text(), 'Go to')]",
                        "//button[contains(text(), 'Continue')]"
                    ]
                    
                    for selector in redirect_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, selector)
                            for element in elements:
                                if element.is_displayed() and element.is_enabled():
                                    element.click()
                                    time.sleep(5)
                                    current_url = self.driver.current_url
                                    logging.info(f"Clicked redirect element, new URL: {current_url}")
                                    break
                            if "?goto=" not in current_url:
                                break
                        except:
                            continue
                except Exception as e:
                    logging.warning(f"Could not find redirect element: {str(e)}")
        
        # Check if we're on a login page or still on redirect
        if "login" in current_url.lower() or "signin" in current_url.lower() or "?goto=" in current_url:
            logging.warning(f"Detected login page or redirect for marketing page. Manual login required.")
            print(f"\nManual login required for marketing page")
            print("Please:")
            print("1. Log in to SteamWorks in the browser window")
            print("2. Navigate to the marketing page manually if needed")
            print("3. Press Enter here when ready...")
            input("Press Enter after logging in...")
            
            # Try to navigate again after manual login
            logging.info(f"Navigating to marketing page again after manual login...")
            self.driver.get(url)
            time.sleep(5)
            
            # Check again
            current_url = self.driver.current_url
            logging.info(f"Current URL after manual login: {current_url}")
            
            # Verify we're on the actual marketing page
            if "navtrafficstats" in current_url and "?goto=" not in current_url:
                logging.info(f"Successfully accessed marketing page after manual login")
                return True
            else:
                logging.error(f"Still not on marketing page after manual login: {current_url}")
                return False
        else:
            # Verify we're on the actual marketing page
            if "navtrafficstats" in current_url and "?goto=" not in current_url:
                logging.info(f"Successfully accessed marketing page")
                return True
            else:
                logging.warning(f"Not on expected marketing page: {current_url}")
                return False
    
    def construct_url_for_date(self, target_date):
        """
        Construct the marketing page URL with date parameters
        
        Format: https://partner.steamgames.com/apps/navtrafficstats/{app_id}?attribution_filter=all&preset_date_range=custom&start_date=MM%2FDD%2FYYYY&end_date=MM%2FDD%2FYYYY
        """
        # Format date as MM/DD/YYYY
        date_str = target_date.strftime("%m/%d/%Y")
        
        # URL encode the date (/ becomes %2F)
        encoded_date = quote(date_str, safe='')
        
        # Construct full URL
        url = (f"https://partner.steamgames.com/apps/navtrafficstats/{self.steam_app_id}"
               f"?attribution_filter=all&preset_date_range=custom"
               f"&start_date={encoded_date}&end_date={encoded_date}")
        
        return url
    
    def download_html_for_date(self, target_date, index, total):
        """
        Download HTML for a specific date
        
        Args:
            target_date: datetime.date object
            index: Current index (for progress logging)
            total: Total number of dates
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Construct URL
            url = self.construct_url_for_date(target_date)
            logging.info(f"[{index}/{total}] Processing date: {target_date.strftime('%Y-%m-%d')}")
            logging.info(f"URL: {url}")
            
            # Navigate to URL
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(5)  # Initial wait for navigation
            
            # CRITICAL: Verify we actually landed on the marketing page
            current_url = self.driver.current_url
            logging.info(f"After navigation, current URL: {current_url}")
            
            # Check if we're on the wrong page
            if "navtrafficstats" not in current_url.lower():
                logging.error(f"ERROR: Not on marketing page! Current URL: {current_url}")
                logging.error("This usually means:")
                logging.error("  1. Session expired - need to re-login")
                logging.error("  2. Access denied to this app/date")
                logging.error("  3. Redirect happened")
                
                # Try to recover by going back to base page then trying again
                logging.info("Attempting recovery - navigating to base page first...")
                if not self.navigate_to_marketing_page_base():
                    logging.error("Recovery failed")
                    return False
                
                time.sleep(2)
                logging.info(f"Retrying navigation to: {url}")
                self.driver.get(url)
                time.sleep(5)
                
                current_url = self.driver.current_url
                logging.info(f"After retry, current URL: {current_url}")
                
                if "navtrafficstats" not in current_url.lower():
                    logging.error("Still not on marketing page after retry - skipping this date")
                    return False
            
            # Check if we're on login page
            if "login" in current_url.lower():
                logging.error("Redirected to login page - authentication required")
                print("\n" + "="*60)
                print("MANUAL LOGIN REQUIRED")
                print("="*60)
                print("Please log in to SteamWorks in the browser window")
                print("After logging in, press Enter to continue...")
                input()
                
                # Try navigating again
                self.driver.get(url)
                time.sleep(15)
                
                current_url = self.driver.current_url
                logging.info(f"After login, current URL: {current_url}")
            
            # Wait for dynamic content to load
            try:
                # Try to wait for specific elements that indicate the page loaded
                try:
                    self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "store_traffic_stats_table")))
                    logging.info("✓ Main table detected")
                except:
                    logging.info("Main table element not found, but continuing...")
                
                # Additional wait to ensure dynamic content loads
                time.sleep(10)  # Wait for AJAX/dynamic content
                
            except Exception as e:
                logging.warning(f"Wait exception: {str(e)}")
            
            # Get page source
            html_content = self.driver.page_source
            
            # Verify we got actual content (not an error page or homepage)
            if len(html_content) < 1000:
                logging.warning(f"HTML content seems too short ({len(html_content)} bytes) - may be an error")
                return False
            
            # Verify this is actually marketing page content
            content_lower = html_content.lower()
            if "store_traffic_stats" not in content_lower and "navtrafficstats" not in content_lower:
                logging.error("HTML does not contain marketing page markers - likely wrong page!")
                logging.error(f"Content length: {len(html_content)} bytes")
                logging.error(f"Current URL: {self.driver.current_url}")
                
                # Check if it's the homepage
                if "steamworks is a set of tools" in content_lower:
                    logging.error("This is the SteamWorks homepage - session or navigation failed")
                
                return False
            
            # Save to file
            filename = f"marketing_{target_date.strftime('%Y-%m-%d')}.html"
            filepath = os.path.join(self.output_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            file_size = os.path.getsize(filepath) / 1024  # Size in KB
            logging.info(f"✓ Saved: {filename} ({file_size:.1f} KB)")
            logging.info(f"  Content verified - contains marketing data")
            
            # Small delay between requests
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logging.error(f"Error downloading HTML for {target_date}: {str(e)}")
            return False
    
    def run(self):
        """Main execution method"""
        start_time = time.time()
        
        try:
            logging.info("="*60)
            logging.info(f"Starting HTML Download for {self.game_name}")
            logging.info(f"App ID: {self.steam_app_id}")
            logging.info(f"Start Date: {self.start_date}")
            logging.info(f"Number of Days: {self.num_days}")
            logging.info("="*60)
            
            # Setup Chrome driver
            self.setup_driver()
            
            # Warmup session
            self.warmup_session()
            
            # Ensure partner context
            self.ensure_partner_context()
            
            # CRITICAL: Navigate to base marketing page first to establish session
            logging.info("Establishing session by navigating to base marketing page...")
            if not self.navigate_to_marketing_page_base():
                logging.error("Failed to navigate to base marketing page - cannot continue")
                return False
            
            logging.info("Session established successfully!")
            time.sleep(2)
            
            # Generate list of dates
            dates_to_process = []
            current_date = self.start_date
            for i in range(self.num_days):
                dates_to_process.append(current_date)
                current_date += timedelta(days=1)
            
            logging.info(f"Generated {len(dates_to_process)} dates to process")
            
            # Download HTML for each date
            successful = 0
            failed = 0
            
            for i, target_date in enumerate(dates_to_process, 1):
                success = self.download_html_for_date(target_date, i, len(dates_to_process))
                if success:
                    successful += 1
                else:
                    failed += 1
            
            # Summary
            total_time = time.time() - start_time
            logging.info("="*60)
            logging.info("DOWNLOAD COMPLETE")
            logging.info("="*60)
            logging.info(f"Total dates: {len(dates_to_process)}")
            logging.info(f"Successful: {successful}")
            logging.info(f"Failed: {failed}")
            logging.info(f"Total time: {total_time:.1f} seconds")
            logging.info(f"Output folder: {self.output_folder}")
            logging.info("="*60)
            
            return True
            
        except Exception as e:
            logging.error(f"Download process failed: {str(e)}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver closed")

def main():
    """Main function"""
    # Configuration
    steam_app_id = 2507950  # Delta Force
    game_name = "Delta Force"
    start_date = datetime(2024, 12, 5).date()  # December 5, 2024
    num_days = 30  # 30 consecutive days
    
    print("\n" + "="*60)
    print("SteamWorks Marketing HTML Downloader")
    print("="*60)
    print(f"Game: {game_name} (App ID: {steam_app_id})")
    print(f"Start Date: {start_date}")
    print(f"Days to Download: {num_days}")
    print(f"End Date: {start_date + timedelta(days=num_days-1)}")
    print("="*60)
    print()
    
    # Create downloader
    downloader = MarketingHTMLDownloader(
        steam_app_id=steam_app_id,
        game_name=game_name,
        start_date=start_date,
        num_days=num_days
    )
    
    # Run download
    success = downloader.run()
    
    if success:
        print("\n✓ Download completed successfully!")
        print(f"Check the 'sample marketing html files' folder for your HTML files")
    else:
        print("\n✗ Download failed - check download_marketing_html.log for details")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())

