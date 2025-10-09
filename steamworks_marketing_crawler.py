from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import mysql.connector
from mysql.connector import Error
import json
import time
import logging
from datetime import date, datetime, timedelta
import os
import shutil
from urllib.parse import quote
import re
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None
import tempfile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('steamworks_marketing_crawler.log'),
        logging.StreamHandler()
    ]
)

class SteamworksMarketingCrawler:
    def __init__(self, db_config, steam_app_id, game_name):
        self.db_config = db_config
        self.steam_app_id = steam_app_id
        self.game_name = game_name
        self.driver = None
        self.wait = None
        
    def setup_driver(self):
        """Setup Chrome with persistent user data directory to retain login"""
        chrome_options = Options()
        
        # Decide which Chrome profile to use
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
                clone_root = os.path.join(os.path.dirname(__file__), 'chrome_profile_clone')
                src_profile_dir = os.path.join(system_user_data, profile_name)
                dst_profile_dir = os.path.join(clone_root, profile_name)
                try:
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
            # Use the same Chrome profile as the financial crawler
            profile_dir = os.path.join(os.path.dirname(__file__), 'chrome_profile')
            try:
                os.makedirs(profile_dir, exist_ok=True)
            except Exception:
                pass
            chrome_options.add_argument(f"--user-data-dir={profile_dir}")
            chrome_options.add_argument("--profile-directory=Default")

        # Stealth-ish flags to reduce automation detection without heavy dependencies
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        # Use a common desktop UA
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
        
        # Don't run headless so user can manually log in
        # chrome_options.add_argument("--headless")
        
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
        """Switch to the correct partner account if needed (View as: select)."""
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
            time.sleep(2)  # Allow page to submit and reload

            # Verify switched
            try:
                # Re-locate after potential reload
                selects_after = self.driver.find_elements(By.XPATH, "//select[@name='runasPubid']")
                if selects_after:
                    select_after = selects_after[0]
                    for opt in select_after.find_elements(By.XPATH, ".//option"):
                        if opt.get_attribute('selected') or opt.is_selected():
                            sel_txt = opt.text.strip()
                            sel_val = (opt.get_attribute('value') or '').strip()
                            logging.info(f"Partner context now: {sel_txt} (id={sel_val})")
                            break
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"ensure_partner_context failed: {str(e)}")


    def navigate_to_marketing_page(self):
        """Navigate to the marketing traffic stats page and handle login if needed"""
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
    
    def set_custom_date_filter(self):
        """Set the time filter to 'Custom' and set both dates to stat_date"""
        try:
            logging.info("Setting time filter to 'Custom' with single-day date...")
            
            # Calculate the stat_date (yesterday in Pacific time)
            from datetime import date, datetime, timedelta
            try:
                from zoneinfo import ZoneInfo
                now_pt = datetime.now(ZoneInfo('America/Los_Angeles'))
                stat_date = (now_pt - timedelta(days=1)).date()
            except ImportError:
                # Fallback to system local time minus one day
                stat_date = (datetime.now() - timedelta(days=1)).date()
            
            # Format the date as MM/DD/YYYY (US format)
            date_str = stat_date.strftime("%m/%d/%Y")
            logging.info(f"Setting custom date filter to: {date_str}")
            
            # Look for the date range selector dropdown
            try:
                # Find the select element with id "PresetDateRange"
                select_element = self.driver.find_element(By.ID, "PresetDateRange")
                
                # Find the "Custom" option
                custom_option = select_element.find_element(By.XPATH, ".//option[@value='custom']")
                
                # Select the custom option
                custom_option.click()
                time.sleep(2)  # Wait for date fields to update
                
                # Set both start_date and end_date to the same date
                start_date_input = self.driver.find_element(By.ID, "start_date")
                end_date_input = self.driver.find_element(By.ID, "end_date")
                
                # Clear and set start_date
                start_date_input.clear()
                time.sleep(1)
                start_date_input.send_keys(date_str)
                time.sleep(1)
                
                # Clear and set end_date
                end_date_input.clear()
                time.sleep(1)
                end_date_input.send_keys(date_str)
                time.sleep(1)
                
                # Verify both dates were set correctly
                start_date_after = start_date_input.get_attribute("value")
                end_date_after = end_date_input.get_attribute("value")
                logging.info(f"Set custom dates - start_date: {start_date_after}, end_date: {end_date_after}")
                
                # Click the "Go" button to apply the custom filter
                go_button = self.driver.find_element(By.ID, "FilterButton")
                logging.info("Clicking Go button to apply custom date filter...")
                go_button.click()
                time.sleep(15)  # Wait longer for data to update
                
                logging.info(f"Successfully set custom single-day filter: {date_str}")
                return True
                    
            except Exception as e:
                logging.warning(f"Could not set custom date filter: {str(e)}")
                return False
                
            except Exception as e:
                logging.warning(f"Could not find date range dropdown: {str(e)}")
                return False
            
        except Exception as e:
            logging.warning(f"Error setting custom date filter: {str(e)}")
            return False
    
    def parse_number_with_suffix(self, text):
        """Parse numbers with suffixes like '46.54 million' to proper integers"""
        if not text:
            return 0
            
        # Remove commas and extract number + suffix
        match = re.search(r'([\d,]+\.?\d*)\s*(million|thousand|billion)?', text.lower())
        if match:
            number_str = match.group(1).replace(',', '')
            suffix = match.group(2) if match.group(2) else ''
            
            number = float(number_str)
            if suffix == 'million':
                return int(number * 1_000_000)
            elif suffix == 'thousand':
                return int(number * 1_000)
            elif suffix == 'billion':
                return int(number * 1_000_000_000)
            else:
                return int(number)
        return 0
    
    def parse_number_with_commas(self, text):
        """Parse numbers with commas like '8,713,638' to integers"""
        if not text:
            return 0
        try:
            return int(text.replace(',', ''))
        except ValueError:
            return 0
    
    def extract_owner_percentage_from_html(self):
        """Extract owner percentage from HTML source by parsing JavaScript"""
        try:
            # Get the page source
            page_source = self.driver.page_source
            
            # Look for the dataOwners JavaScript array
            import re
            pattern = r'var dataOwners = \[(.*?)\];'
            match = re.search(pattern, page_source, re.DOTALL)
            
            if match:
                data_owners_str = match.group(1)
                # Parse the array content
                # Expected format: [ 'Non-Owners: 74.2%',  74.2 ], [ 'Owners: 25.8%',  25.8 ]
                
                # Look for the Owners entry
                owners_pattern = r"\[\s*'Owners:\s*([0-9.]+)%',\s*([0-9.]+)\s*\]"
                owners_match = re.search(owners_pattern, data_owners_str)
                
                if owners_match:
                    owner_percentage = float(owners_match.group(2))
                    logging.info(f"Found owner percentage: {owner_percentage}%")
                    return owner_percentage
            
            logging.warning("Could not find owner percentage in HTML source")
            return None
            
        except Exception as e:
            logging.error(f"Failed to extract owner percentage from HTML: {str(e)}")
            return None
    
    def extract_top_country_visits_from_html(self):
        """Extract top country visits from HTML source by parsing dataTicks and dataCountries arrays"""
        try:
            # Get the page source
            page_source = self.driver.page_source
            
            # Look for the dataCountries JavaScript array first
            import re
            countries_pattern = r'var dataCountries\s*=\s*\[(.*?)\];'
            countries_match = re.search(countries_pattern, page_source, re.DOTALL)
            
            if not countries_match:
                logging.warning("Could not find dataCountries array in HTML source")
                return None
            
            # Extract visit numbers from dataCountries
            visits_str = countries_match.group(1)
            visits_pattern = r'(\d+)'
            visits_numbers = re.findall(visits_pattern, visits_str)
            visits_numbers = [int(v) for v in visits_numbers]
            
            # Look for the dataTicks JavaScript array
            ticks_pattern = r'var dataTicks\s*=\s*\[(.*?)\];'
            ticks_match = re.search(ticks_pattern, page_source, re.DOTALL)
            
            if not ticks_match:
                logging.warning("Could not find dataTicks array in HTML source")
                return None
            
            data_ticks_str = ticks_match.group(1)
            # Parse the array content
            # Expected format: "Hong Kong, 17%","China, 17%","United States, 12%",...
            
            # Extract individual entries
            entries_pattern = r'"([^"]+)"'
            entries = re.findall(entries_pattern, data_ticks_str)
            
            # Verify that we have matching counts
            if len(entries) != len(visits_numbers):
                logging.warning(f"Mismatch between country entries ({len(entries)}) and visit numbers ({len(visits_numbers)})")
                return None
            
            country_data = []
            for rank, entry in enumerate(entries):
                try:
                    # Split by comma to separate country and percentage
                    if ',' in entry:
                        country_part, percentage_part = entry.rsplit(',', 1)
                        country = country_part.strip()
                        
                        # Extract percentage number (remove % symbol)
                        percentage_match = re.search(r'([0-9.]+)%?', percentage_part.strip())
                        if percentage_match:
                            percentage = float(percentage_match.group(1))
                            visits = visits_numbers[rank]  # Get corresponding visit number
                            
                            country_data.append({
                                'country': country,
                                'percentage': percentage,
                                'visits': visits,
                                'rank': rank + 1
                            })
                except Exception as e:
                    logging.warning(f"Failed to parse country entry '{entry}': {str(e)}")
                    continue
            
            if country_data:
                logging.info(f"Found {len(country_data)} countries in top_country_visits")
                return country_data
            else:
                logging.warning("No valid country data found in dataTicks")
                return None
            
        except Exception as e:
            logging.error(f"Failed to extract top country visits from HTML: {str(e)}")
            return None
    
    def extract_all_source_breakdown_from_html(self):
        """Extract all source breakdown data from HTML source by parsing all first-level rows"""
        try:
            # Get the page source
            page_source = self.driver.page_source
            import re
            
            # Look for all first-level rows (highlightHover page_stats)
            # These are the main table rows that can be expanded
            first_level_pattern = r'<div class="tr highlightHover page_stats".*?onclick="ToggleFeatureStats.*?</div>\s*</div>'
            first_level_matches = re.findall(first_level_pattern, page_source, re.DOTALL)
            
            if not first_level_matches:
                logging.warning("Could not find any first-level rows in HTML source")
                return None
            
            logging.info(f"Found {len(first_level_matches)} first-level rows")
            
            all_source_data = []
            
            # Process each first-level row
            for row_html in first_level_matches:
                try:
                    # Extract page/feature name
                    name_pattern = r'<strong>([^<]+)</strong>'
                    name_match = re.search(name_pattern, row_html)
                    if not name_match:
                        continue
                    
                    page_feature = name_match.group(1).strip()
                    
                    # Extract all td values in the correct order
                    # Find all td elements that contain data (not the title or expander)
                    td_pattern = r'<div class="td"[^>]*>([^<]*)</div>'
                    all_td_matches = re.findall(td_pattern, row_html)
                    
                    # Filter out the title (first td) and expander (last td), keep only data values
                    data_values = []
                    for i, value in enumerate(all_td_matches):
                        clean_value = value.strip()
                        # Skip empty values, title, and expander
                        if (clean_value and 
                            clean_value != page_feature and  # Skip the title
                            'expander' not in clean_value and  # Skip expander
                            (clean_value.replace(',', '').replace('.', '').replace('%', '').isdigit() or 
                             '.' in clean_value.replace('%', '') or 
                             ',' in clean_value)):
                            data_values.append(clean_value)
                    
                    # Initialize row data with default values
                    row_data = {
                        'page_feature': page_feature,
                        'impressions': 0,
                        'owner_impressions': 0,
                        'percentage_of_total_impressions': 0.0,
                        'click_thru_rate': 0.0,
                        'visits': 0,
                        'owner_visits': 0,
                        'percentage_of_total_visits': 0.0
                    }
                    
                    # Map the available values to the correct fields (use 0 for missing values)
                    field_names = ['impressions', 'owner_impressions', 'percentage_of_total_impressions', 
                                  'click_thru_rate', 'visits', 'owner_visits', 'percentage_of_total_visits']
                    
                    for i, value in enumerate(data_values):
                        if i < len(field_names):
                            field_name = field_names[i]
                            
                            if not value.strip():
                                row_data[field_name] = 0
                            else:
                                # Remove commas and extract number
                                clean_value = value.strip().replace(',', '')
                                if clean_value.endswith('%'):
                                    # Percentage value
                                    num_match = re.search(r'([0-9.]+)%?', clean_value)
                                    row_data[field_name] = float(num_match.group(1)) if num_match else 0
                                else:
                                    # Regular number
                                    try:
                                        row_data[field_name] = int(clean_value)
                                    except ValueError:
                                        row_data[field_name] = 0
                    
                    all_source_data.append(row_data)
                    logging.info(f"Processed first-level row: {page_feature} with {len(data_values)} values")
                        
                except Exception as e:
                    logging.warning(f"Failed to parse first-level row: {str(e)}")
                    continue
            
            if all_source_data:
                logging.info(f"All source breakdown: extracted {len(all_source_data)} rows")
                return all_source_data
            else:
                logging.warning("No valid first-level rows found")
                return None
            
        except Exception as e:
            logging.error(f"Failed to extract all source breakdown from HTML: {str(e)}")
            return None
    
    def extract_homepage_breakdown_from_html(self):
        """Extract homepage breakdown data from HTML source by parsing Home Page expanded section"""
        try:
            # Get the page source
            page_source = self.driver.page_source
            import re
            
            # Look for Home Page expanded section (featurestatsclass_3)
            # Pattern matches rows with class "feature_stats featurestatsclass_3"
            homepage_pattern = r'<div class="tr feature_stats featurestatsclass_3".*?</div>\s*</div>'
            homepage_matches = re.findall(homepage_pattern, page_source, re.DOTALL)
            
            if not homepage_matches:
                logging.warning("Could not find Home Page expanded section in HTML source")
                return None
            
            logging.info(f"Found {len(homepage_matches)} Home Page expanded rows")
            
            homepage_data = []
            
            # Process each expanded row
            for row_html in homepage_matches:
                try:
                    # Extract page/feature name
                    name_pattern = r'<strong>([^<]+)</strong>'
                    name_match = re.search(name_pattern, row_html)
                    if not name_match:
                        continue
                    
                    
                    page_feature = name_match.group(1).strip()
                    
                    # Extract all td values in the correct order
                    # Find all td elements that contain data (not the title)
                    td_pattern = r'<div class="td"[^>]*>([^<]*)</div>'
                    all_td_matches = re.findall(td_pattern, row_html)
                    
                    # Filter out the title (first td), keep only data values
                    data_values = []
                    for i, value in enumerate(all_td_matches):
                        clean_value = value.strip()
                        # Skip empty values and title
                        if (clean_value and 
                            clean_value != page_feature and  # Skip the title
                            (clean_value.replace(',', '').replace('.', '').replace('%', '').isdigit() or 
                             '.' in clean_value.replace('%', '') or 
                             ',' in clean_value)):
                            data_values.append(clean_value)
                    
                    # Initialize row data with default values (include all rows regardless of data count)
                    row_data = {
                        'page_feature': page_feature,
                        'impressions': 0,
                        'owner_impressions': 0,
                        'percentage_of_total_impressions': 0.0,
                        'click_thru_rate': 0.0,
                        'visits': 0,
                        'owner_visits': 0,
                        'percentage_of_total_visits': 0.0
                    }
                    
                    # Map the available values to the correct fields (use 0 for missing values)
                    field_names = ['impressions', 'owner_impressions', 'percentage_of_total_impressions', 
                                  'click_thru_rate', 'visits', 'owner_visits', 'percentage_of_total_visits']
                    
                    for i, value in enumerate(data_values):
                        if i < len(field_names):
                            field_name = field_names[i]
                            
                            if not value.strip():
                                row_data[field_name] = 0
                            else:
                                # Remove commas and extract number
                                clean_value = value.strip().replace(',', '')
                                if clean_value.endswith('%'):
                                    # Percentage value
                                    num_match = re.search(r'([0-9.]+)%?', clean_value)
                                    row_data[field_name] = float(num_match.group(1)) if num_match else 0
                                else:
                                    # Regular number
                                    try:
                                        row_data[field_name] = int(clean_value)
                                    except ValueError:
                                        row_data[field_name] = 0
                    
                    homepage_data.append(row_data)
                    logging.info(f"Processed Home Page expanded row: {page_feature} with {len(data_values)} values")
                        
                except Exception as e:
                    logging.warning(f"Failed to parse Home Page expanded row: {str(e)}")
                    continue
            
            if homepage_data:
                logging.info(f"Homepage breakdown: extracted {len(homepage_data)} rows")
                return homepage_data
            else:
                logging.warning("No valid Home Page expanded rows found")
                return None
            
        except Exception as e:
            logging.error(f"Failed to extract homepage breakdown from HTML: {str(e)}")
            return None
    
    def extract_takeover_banner_from_breakdown(self, homepage_breakdown):
        """Extract takeover banner data from homepage_breakdown JSON"""
        try:
            if not homepage_breakdown:
                logging.warning("No homepage breakdown data available for takeover banner extraction")
                return None
            
            # Find the takeover banner entry in homepage breakdown
            for entry in homepage_breakdown:
                if entry.get('page_feature') == 'Takeover Banner':
                    # Apply threshold check: if impressions < 1000, return None
                    if entry.get('impressions', 0) >= 1000:
                        logging.info(f"Found Takeover Banner: impressions={entry.get('impressions')}, visits={entry.get('visits')}")
                        return entry
                    else:
                        logging.info(f"Takeover Banner impressions ({entry.get('impressions', 0)}) below threshold (1000), skipping")
                        return None
            
            logging.warning("Could not find Takeover Banner entry in homepage breakdown")
            return None
            
        except Exception as e:
            logging.error(f"Failed to extract takeover banner from breakdown: {str(e)}")
            return None
    
    def extract_main_cluster_from_breakdown(self, homepage_breakdown):
        """Extract and aggregate main cluster data from homepage_breakdown JSON"""
        try:
            if not homepage_breakdown:
                logging.warning("No homepage breakdown data available for main cluster extraction")
                return None
            
            # Find all main cluster entries
            main_cluster_entries = []
            for entry in homepage_breakdown:
                page_feature = entry.get('page_feature', '')
                if page_feature.startswith('Main Cluster ('):
                    main_cluster_entries.append(entry)
            
            if not main_cluster_entries:
                logging.warning("Could not find any Main Cluster entries in homepage breakdown")
                return None
            
            logging.info(f"Found {len(main_cluster_entries)} Main Cluster entries")
            
            # Aggregate the data
            aggregated_data = {
                'impressions': 0,
                'owner_impressions': 0,
                'percentage_of_total_impressions': 0.0,
                'click_thru_rate': 0.0,
                'visits': 0,
                'owner_visits': 0,
                'percentage_of_total_visits': 0.0
            }
            
            # Sum up all main cluster data
            for entry in main_cluster_entries:
                aggregated_data['impressions'] += entry.get('impressions', 0)
                aggregated_data['owner_impressions'] += entry.get('owner_impressions', 0)
                aggregated_data['percentage_of_total_impressions'] += entry.get('percentage_of_total_impressions', 0)
                aggregated_data['click_thru_rate'] += entry.get('click_thru_rate', 0)
                aggregated_data['visits'] += entry.get('visits', 0)
                aggregated_data['owner_visits'] += entry.get('owner_visits', 0)
                aggregated_data['percentage_of_total_visits'] += entry.get('percentage_of_total_visits', 0)
                
                logging.info(f"Processed Main Cluster '{entry.get('page_feature')}': impressions={entry.get('impressions')}, visits={entry.get('visits')}")
            
            # Calculate average click-thru rate
            if len(main_cluster_entries) > 0:
                aggregated_data['click_thru_rate'] = round(aggregated_data['click_thru_rate'] / len(main_cluster_entries), 2)
                # Note: percentage_of_total_impressions and percentage_of_total_visits are summed, not averaged
            
            # Apply threshold check: if impressions < 1000, return None
            if aggregated_data['impressions'] < 1000:
                logging.info(f"Main Cluster impressions ({aggregated_data['impressions']}) below threshold (1000), skipping")
                return None
            
            logging.info(f"Main Cluster aggregated data: impressions={aggregated_data['impressions']}, visits={aggregated_data['visits']}")
            return aggregated_data
            
        except Exception as e:
            logging.error(f"Failed to extract main cluster from breakdown: {str(e)}")
            return None
    
    def extract_pop_up_message_from_breakdown(self, all_source_breakdown):
        """Extract pop-up message data from all_source_breakdown JSON"""
        try:
            if not all_source_breakdown:
                logging.warning("No all source breakdown data available for pop-up message extraction")
                return None
            
            # Find the marketing message entry in all source breakdown
            for entry in all_source_breakdown:
                if entry.get('page_feature') == 'Marketing Message':
                    # Apply threshold check: if impressions < 1000, return None
                    if entry.get('impressions', 0) >= 1000:
                        logging.info(f"Found Marketing Message: impressions={entry.get('impressions')}, visits={entry.get('visits')}")
                        return entry
                    else:
                        logging.info(f"Marketing Message impressions ({entry.get('impressions', 0)}) below threshold (1000), skipping")
                        return None
            
            logging.warning("Could not find Marketing Message entry in all source breakdown")
            return None
            
        except Exception as e:
            logging.error(f"Failed to extract pop-up message from breakdown: {str(e)}")
            return None
    
    def extract_basic_metrics(self):
        """Extract the 10 basic metrics from the marketing page"""
        logging.info("Extracting basic metrics...")
        
        # Debug: Check current date range on page before extraction
        try:
            # Look for the specific date range format from the sample HTML
            date_elements = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'GMT')]")
            for elem in date_elements:
                logging.info(f"Date range on page before extraction: {elem.text}")
            
            # Also check for any date-related text
            all_text = self.driver.page_source
            if "GMT" in all_text:
                import re
                gmt_matches = re.findall(r'[A-Za-z]{3}\s+\d{2},\s+\d{4}.*?GMT', all_text)
                for match in gmt_matches:
                    logging.info(f"Found GMT date range: {match}")
        except Exception as e:
            logging.warning(f"Could not find date range: {str(e)}")
        
        try:
            # 1. Extract total_impressions
            impressions_element = WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@class='stats_header_section']//div[contains(text(), 'Impressions')]/following-sibling::div[@class='stat']")
                )
            )
            impressions_text = impressions_element.text.strip()
            total_impressions = self.parse_number_with_suffix(impressions_text)
            logging.info(f"Extracted total_impressions: {total_impressions}")
            
            # 2. Extract total_visits  
            visits_element = self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@class='stats_header_section']//div[contains(text(), 'Visits')]/following-sibling::div[@class='stat']")
                )
            )
            visits_text = visits_element.text.strip()
            total_visits = self.parse_number_with_commas(visits_text)
            logging.info(f"Extracted total_visits: {total_visits}")
            
            # 3. Calculate total_click_through_rate
            if total_impressions > 0:
                total_click_through_rate = round((total_visits / total_impressions) * 100, 2)
            else:
                total_click_through_rate = 0
            logging.info(f"Calculated total_click_through_rate: {total_click_through_rate}%")
            
            # 4. Extract owner_visits from HTML source
            owner_visits = self.extract_owner_percentage_from_html()
            logging.info(f"Extracted owner_visits: {owner_visits}")
            
            # 5. Extract top_country_visits from HTML source
            top_country_visits = self.extract_top_country_visits_from_html()
            logging.info(f"Extracted top_country_visits: {len(top_country_visits) if top_country_visits else 0} countries")
            
            # 6. Extract all_source_breakdown from HTML source
            all_source_breakdown = self.extract_all_source_breakdown_from_html()
            logging.info(f"Extracted all_source_breakdown: {'success' if all_source_breakdown else 'not found'}")
            
            # 7. Extract homepage_breakdown from HTML source
            homepage_breakdown = self.extract_homepage_breakdown_from_html()
            logging.info(f"Extracted homepage_breakdown: {'success' if homepage_breakdown else 'not found'}")
            
            # 8. Extract main_cluster from homepage_breakdown JSON
            main_cluster = self.extract_main_cluster_from_breakdown(homepage_breakdown)
            logging.info(f"Extracted main_cluster: {'success' if main_cluster else 'skipped/not found'}")
            
            # 9. Extract takeover_banner from homepage_breakdown JSON
            takeover_banner = self.extract_takeover_banner_from_breakdown(homepage_breakdown)
            logging.info(f"Extracted takeover_banner: {'success' if takeover_banner else 'skipped/not found'}")
            
            # 10. Extract pop_up_message from all_source_breakdown JSON
            pop_up_message = self.extract_pop_up_message_from_breakdown(all_source_breakdown)
            logging.info(f"Extracted pop_up_message: {'success' if pop_up_message else 'skipped/not found'}")
            
            return {
                'total_impressions': total_impressions,
                'total_visits': total_visits, 
                'total_click_through_rate': total_click_through_rate,
                'owner_visits': owner_visits,
                'top_country_visits': top_country_visits,
                'main_cluster': main_cluster,
                'takeover_banner': takeover_banner,
                'pop_up_message': pop_up_message,
                'all_source_breakdown': all_source_breakdown,
                'homepage_breakdown': homepage_breakdown
            }
            
        except Exception as e:
            logging.error(f"Failed to extract basic metrics: {str(e)}")
            return {
                'total_impressions': None,
                'total_visits': None, 
                'total_click_through_rate': None,
                'owner_visits': None,
                'top_country_visits': None,
                'main_cluster': None,
                'takeover_banner': None,
                'pop_up_message': None,
                'all_source_breakdown': None,
                'homepage_breakdown': None
            }
    
    def get_game_table_name(self):
        """Get the game-specific table name based on steam_app_id"""
        game_tables = {
            2507950: 'delta_force_daily_marketing',
            3104410: 'terminull_brigade_daily_marketing',
            3478050: 'road_to_empress_daily_marketing'
        }
        return game_tables.get(self.steam_app_id)
    
    def store_marketing_data(self, data):
        """Store marketing data in both overall and game-specific tables"""
        connection = None
        cursor = None
        
        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor()
            
            # Get current date (same calculation as date filter - Pacific timezone)
            from datetime import date, datetime, timedelta
            try:
                from zoneinfo import ZoneInfo
                now_pt = datetime.now(ZoneInfo('America/Los_Angeles'))
                current_date = (now_pt - timedelta(days=1)).date()
                logging.info(f"Using Pacific timezone - stat_date: {current_date}")
            except ImportError:
                # Fallback to system local time minus one day
                current_date = date.today() - timedelta(days=1)
                logging.info(f"Using system timezone - stat_date: {current_date}")
            
            # Prepare data for insertion
            insert_data = {
                'steam_app_id': self.steam_app_id,
                'game_name': self.game_name,
                'stat_date': current_date,
                'total_impressions': data.get('total_impressions'),
                'total_visits': data.get('total_visits'),
                'total_click_through_rate': data.get('total_click_through_rate'),
                'owner_visits': data.get('owner_visits'),
                'top_country_visits': json.dumps(data.get('top_country_visits')) if data.get('top_country_visits') else None,
                'takeover_banner': json.dumps(data.get('takeover_banner')) if data.get('takeover_banner') else None,
                'pop_up_message': json.dumps(data.get('pop_up_message')) if data.get('pop_up_message') else None,
                'main_cluster': json.dumps(data.get('main_cluster')) if data.get('main_cluster') else None,
                'all_source_breakdown': json.dumps(data.get('all_source_breakdown')) if data.get('all_source_breakdown') else None,
                'homepage_breakdown': json.dumps(data.get('homepage_breakdown')) if data.get('homepage_breakdown') else None
            }
            
            # Insert into overall table
            overall_query = """
                INSERT INTO game_daily_marketing 
                (steam_app_id, game_name, stat_date, total_impressions, total_visits, 
                 total_click_through_rate, owner_visits, top_country_visits, takeover_banner, 
                 pop_up_message, main_cluster, all_source_breakdown, homepage_breakdown)
                VALUES (%(steam_app_id)s, %(game_name)s, %(stat_date)s, %(total_impressions)s, 
                        %(total_visits)s, %(total_click_through_rate)s, %(owner_visits)s, 
                        %(top_country_visits)s, %(takeover_banner)s, %(pop_up_message)s, 
                        %(main_cluster)s, %(all_source_breakdown)s, %(homepage_breakdown)s)
                ON DUPLICATE KEY UPDATE
                    total_impressions = VALUES(total_impressions),
                    total_visits = VALUES(total_visits),
                    total_click_through_rate = VALUES(total_click_through_rate),
                    owner_visits = VALUES(owner_visits),
                    top_country_visits = VALUES(top_country_visits),
                    takeover_banner = VALUES(takeover_banner),
                    pop_up_message = VALUES(pop_up_message),
                    main_cluster = VALUES(main_cluster),
                    all_source_breakdown = VALUES(all_source_breakdown),
                    homepage_breakdown = VALUES(homepage_breakdown),
                    updated_at = CURRENT_TIMESTAMP
            """
            
            cursor.execute(overall_query, insert_data)
            logging.info(f"Inserted data into game_daily_marketing for {self.game_name}")
            
            # Insert into game-specific table
            game_table = self.get_game_table_name()
            if game_table:
                game_query = f"""
                    INSERT INTO {game_table} 
                    (steam_app_id, game_name, stat_date, total_impressions, total_visits, 
                     total_click_through_rate, owner_visits, top_country_visits, takeover_banner, 
                     pop_up_message, main_cluster, all_source_breakdown, homepage_breakdown)
                    VALUES (%(steam_app_id)s, %(game_name)s, %(stat_date)s, %(total_impressions)s, 
                            %(total_visits)s, %(total_click_through_rate)s, %(owner_visits)s, 
                            %(top_country_visits)s, %(takeover_banner)s, %(pop_up_message)s, 
                            %(main_cluster)s, %(all_source_breakdown)s, %(homepage_breakdown)s)
                    ON DUPLICATE KEY UPDATE
                        total_impressions = VALUES(total_impressions),
                        total_visits = VALUES(total_visits),
                        total_click_through_rate = VALUES(total_click_through_rate),
                        owner_visits = VALUES(owner_visits),
                        top_country_visits = VALUES(top_country_visits),
                        takeover_banner = VALUES(takeover_banner),
                        pop_up_message = VALUES(pop_up_message),
                        main_cluster = VALUES(main_cluster),
                        all_source_breakdown = VALUES(all_source_breakdown),
                        homepage_breakdown = VALUES(homepage_breakdown),
                        updated_at = CURRENT_TIMESTAMP
                """
                
                cursor.execute(game_query, insert_data)
                logging.info(f"Inserted data into {game_table} for {self.game_name}")
            else:
                logging.warning(f"No game-specific table found for steam_app_id: {self.steam_app_id}")
            
            connection.commit()
            logging.info("Marketing data stored successfully")
            
        except Error as e:
            logging.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Error storing marketing data: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
    
    def run_crawler(self):
        """Main execution method"""
        start_time = time.time()
        
        try:
            logging.info(f"Starting marketing crawler for {self.game_name} ({self.steam_app_id})")
            
            # Setup Chrome driver
            self.setup_driver()
            # Warmup: open SteamWorks home once to ensure proper session
            self.warmup_session()
            # Ensure we are viewing as the target partner account
            self.ensure_partner_context()
            
            # Navigate to marketing page
            if not self.navigate_to_marketing_page():
                logging.error("Failed to access marketing page - login verification failed")
                return False, "Failed to access marketing page - please ensure you are logged in"
            
            # Set custom date filter for single-day data
            filter_success = self.set_custom_date_filter()
            if not filter_success:
                logging.warning("Could not set custom date filter, proceeding with current data")
            
            # Extract basic metrics
            basic_metrics = self.extract_basic_metrics()
            
            if basic_metrics:
                # Store data
                self.store_marketing_data(basic_metrics)
                logging.info(f"Marketing crawler completed successfully for {self.game_name}")
                return True, basic_metrics
            else:
                logging.error("✗ Failed to extract any marketing data")
                return False, "Data extraction failed"
                
        except Exception as e:
            logging.error(f"Marketing crawler failed for {self.game_name}: {str(e)}")
            return False, str(e)
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver closed")

def main():
    """Main function to run the marketing crawler"""
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'database': 'steamworks_crawler',
        'user': 'root',
        'password': 'Zh1149191843!'
    }
    
    # Games to run (same as financial crawler)
    games_env = os.environ.get('STEAMWORKS_GAMES', '').strip()
    games = []
    if games_env:
        try:
            parts = [p for p in games_env.split(',') if p.strip()]
            for p in parts:
                if ':' in p:
                    app_id_str, name = p.split(':', 1)
                    app_id = int(app_id_str.strip())
                    games.append((app_id, name.strip()))
        except Exception:
            games = []
    if not games:
        # Default games list - testing with Delta Force only
        games = [
            (2507950, 'Delta Force'),
        ]

    overall_success = True
    for app_id, name in games:
        print(f"\n=== Running marketing crawler for {name} ({app_id}) ===")
        crawler = SteamworksMarketingCrawler(db_config, steam_app_id=app_id, game_name=name)
        success, result = crawler.run_crawler()
        if success:
            print("Marketing crawler completed successfully for this game.")
        else:
            print(f"Marketing crawler failed for {name} ({app_id}): {result}")
            overall_success = False

    if overall_success:
        print("\nAll marketing crawls completed.")
    else:
        print("\nSome marketing crawls failed. See logs for details.")

if __name__ == "__main__":
    main()
