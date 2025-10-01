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
        logging.FileHandler('steamworks_crawler.log'),
        logging.StreamHandler()
    ]
)

class SteamWorksCrawler:
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
            # Use a persistent local profile inside repo to retain login across runs
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

    def navigate_to_page(self, url, page_name):
        """Navigate to a specific page and handle login if needed"""
        try:
            logging.info(f"Navigating to {page_name}: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Check current URL to see if we were redirected to login
            current_url = self.driver.current_url
            logging.info(f"Current URL: {current_url}")
            
            # If page shows access denied, retry via login goto route once
            try:
                page_html = (self.driver.page_source or '').lower()
                if ('access denied' in page_html) or ('do not have access' in page_html) or ('error 403' in page_html):
                    logging.warning("Access denied detected. Retrying via login goto route...")
                    # Build goto using path (must be relative on partner site)
                    rel = url.replace('https://partner.steampowered.com', '')
                    goto_url = f"https://partner.steampowered.com/login/?goto={quote(rel)}"
                    self.driver.get(goto_url)
                    time.sleep(3)
                    current_url = self.driver.current_url
                    logging.info(f"After goto route, current URL: {current_url}")
            except Exception:
                pass
            
            # Check if we're on a login page
            if "login" in current_url.lower() or "signin" in current_url.lower():
                logging.warning(f"Detected login page for {page_name}. Manual login required.")
                print(f"\nManual login required for {page_name}")
                print("Please:")
                print("1. Log in to SteamWorks in the browser window")
                print("2. Navigate to the correct page if needed")
                print("3. Press Enter here when ready...")
                input("Press Enter after logging in...")
                
                # Try to navigate again after manual login
                logging.info(f"Navigating to {page_name} again after manual login...")
                self.driver.get(url)
                time.sleep(3)
                
                # Check again
                current_url = self.driver.current_url
                logging.info(f"Current URL after manual login: {current_url}")
                
                if "login" not in current_url.lower() and "signin" not in current_url.lower():
                    logging.info(f"Successfully accessed {page_name} after manual login")
                    return True
                else:
                    logging.error(f"Still on login page after manual login for {page_name}")
                    return False
            else:
                logging.info(f"Successfully accessed {page_name}")
                return True
                
        except Exception as e:
            logging.error(f"Error navigating to {page_name}: {str(e)}")
            return False
    
    def set_yesterday_filter(self):
        """Set the time filter to 'yesterday' on the current page"""
        try:
            logging.info("Setting time filter to 'yesterday'...")
            
            # Look for yesterday button/link
            yesterday_selectors = [
                "//button[contains(text(), 'yesterday')]",
                "//a[contains(text(), 'yesterday')]",
                "//input[contains(@value, 'yesterday')]",
                "//span[contains(text(), 'yesterday')]",
                "//div[contains(text(), 'yesterday')]",
                "//em[contains(text(), 'yesterday')]"
            ]
            
            for selector in yesterday_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            element.click()
                            time.sleep(2)  # Wait for data to update
                            logging.info("Set time filter to 'yesterday'")
                            return True
                except:
                    continue
            
            logging.warning("Could not find 'yesterday' time filter button")
            return False
            
        except Exception as e:
            logging.warning(f"Error setting yesterday filter: {str(e)}")
            return False
    
    def extract_default_page_data(self):
        """Extract data from the Default Game Page"""
        url = f"https://partner.steampowered.com/app/details/{self.steam_app_id}/"
        
        if not self.navigate_to_page(url, "Default Game Page"):
            return None
        
        data = {}
        
        try:
            # Extract Lifetime Unique Users
            logging.info("Extracting Lifetime Unique Users...")
            try:
                # Look for the lifetime unique users data in table format
                selectors = [
                    "//td[contains(text(), 'Lifetime unique users')]/following-sibling::td[@align='right']",
                    "//td[contains(text(), 'Lifetime unique users')]/following-sibling::td[2]"
                ]
                
                unique_users = None
                for selector in selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element.text.strip():
                            unique_users = self.parse_numeric_value(element.text)
                            if unique_users:
                                # Map to schema field
                                data['unique_player'] = unique_users
                                logging.info(f"✓ Found Lifetime Unique Users: {unique_users}")
                                break
                    except:
                        continue
                
                if not unique_users:
                    logging.warning("Failed to get Lifetime Unique Users")
                    
            except Exception as e:
                logging.warning(f"Failed to get Lifetime Unique Users: {str(e)}")
            
            # Extract Wishlists (Outstanding count)
            logging.info("Extracting Wishlists (Outstanding)...")
            try:
                wishlist_selectors = [
                    "//td[normalize-space(text())='Wishlists']/following-sibling::td",
                    "//td[contains(text(), 'Wishlists')]/following-sibling::td"
                ]
                for selector in wishlist_selectors:
                    try:
                        el = self.driver.find_element(By.XPATH, selector)
                        raw = el.text.strip()
                        if raw:
                            # Value may include trailing '+' link
                            first_token = raw.split()[0]
                            val = self.parse_numeric_value(first_token)
                            if val is not None:
                                data['wishlist'] = val
                                logging.info(f"✓ Found Wishlists (Outstanding): {val}")
                                break
                    except:
                        continue
            except Exception as e:
                logging.warning(f"Failed to get Wishlists Outstanding: {str(e)}")

            # Extract Lifetime Total Units
            logging.info("Extracting Lifetime Total Units...")
            try:
                lifetime_units_selectors = [
                    "//td[contains(text(), 'Lifetime total units')]/following-sibling::td[@align='right']",
                    "//td[contains(text(), 'Lifetime total units')]/following-sibling::td[2]"
                ]
                lifetime_units = None
                for selector in lifetime_units_selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element.text.strip():
                            lifetime_units = self.parse_numeric_value(element.text)
                            if lifetime_units is not None:
                                data['lifetime_total_units'] = int(lifetime_units)
                                logging.info(f"✓ Found Lifetime Total Units: {lifetime_units}")
                                break
                    except Exception:
                        continue
                if lifetime_units is None:
                    logging.warning("Failed to get Lifetime Total Units")
            except Exception as e:
                logging.warning(f"Failed to get Lifetime Total Units: {str(e)}")
            
            # Extract Median Time Played
            logging.info("Extracting Median Time Played...")
            try:
                # Look for median time played data in table format
                selectors = [
                    "//td[contains(text(), 'Median time played')]/following-sibling::td[@align='right']",
                    "//td[contains(text(), 'Median time played')]/following-sibling::td[2]"
                ]
                
                median_time = None
                for selector in selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element.text.strip():
                            # Keep as string for schema (VARCHAR)
                            median_time = element.text.strip()
                            if median_time:
                                data['median_playtime'] = median_time
                                logging.info(f"✓ Found Median Time Played: {median_time}")
                                break
                    except:
                        continue
                
                if not median_time:
                    logging.warning("Failed to get Median Time Played")
                    
            except Exception as e:
                logging.warning(f"Failed to get Median Time Played: {str(e)}")
            
            # Extract Lifetime Steam revenue (gross)
            logging.info("Extracting Lifetime Steam revenue (gross)...")
            try:
                lifetime_gross_selectors = [
                    "//td[normalize-space(text())='Lifetime Steam revenue (gross)']/following-sibling::td[@align='right']",
                    "//td[contains(text(), 'Lifetime Steam revenue (gross)')]/following-sibling::td[1]"
                ]
                lifetime_gross = None
                for selector in lifetime_gross_selectors:
                    try:
                        el = self.driver.find_element(By.XPATH, selector)
                        raw = el.text.strip()
                        if raw:
                            # raw like "$56,289,662" → 56289662
                            parsed = self.parse_numeric_value(raw)
                            if parsed is not None:
                                lifetime_gross = int(float(parsed))
                                data['lifetime_total_revenue'] = lifetime_gross
                                logging.info(f"✓ Found Lifetime Steam revenue (gross): {lifetime_gross}")
                                break
                    except Exception:
                        continue
                if lifetime_gross is None:
                    logging.warning("Failed to get Lifetime Steam revenue (gross)")
            except Exception as e:
                logging.warning(f"Failed to get Lifetime Steam revenue (gross): {str(e)}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting data from Default Game Page: {str(e)}")
            return None
    
    def extract_playtime_page_data(self):
        """Extract data from the Lifetime Play Time Page"""
        url = f"https://partner.steampowered.com//app/playtime/{self.steam_app_id}/"
        
        if not self.navigate_to_page(url, "Lifetime Play Time Page"):
            return None
        
        data = {}
        
        try:
            # Extract Playtime Breakdown Table
            logging.info("Extracting Playtime Breakdown Table...")
            try:
                # Look for the playtime breakdown table
                table_selectors = [
                    "//table[contains(@class, 'table')]",
                    "//table",
                    "//div[contains(@class, 'table')]//table"
                ]
                
                playtime_data = {}
                table_found = False
                
                for table_selector in table_selectors:
                    try:
                        tables = self.driver.find_elements(By.XPATH, table_selector)
                        for table in tables:
                            # Look for rows with "Minimum Time Played" and "Percentage of Users"
                            rows = table.find_elements(By.XPATH, ".//tr")
                            for row in rows:
                                cells = row.find_elements(By.XPATH, ".//td")
                                if len(cells) >= 2:
                                    time_cell = cells[0].text.strip()
                                    percentage_cell = cells[1].text.strip()
                                    
                                    # Check if this looks like playtime data
                                    if ('hour' in time_cell.lower() or 'minute' in time_cell.lower()) and '%' in percentage_cell:
                                        playtime_data[time_cell] = self.parse_numeric_value(percentage_cell)
                                        table_found = True
                        
                        if table_found:
                            break
                    except:
                        continue
                
                if playtime_data:
                    logging.info(f"Found Playtime Breakdown: {len(playtime_data)} entries")
                    # Extract players_20h_plus from the "20 hours" row as integer percent
                    try:
                        percent_val = None
                        # Prefer an exact-like key containing '20 hours'
                        for k, v in playtime_data.items():
                            key_l = str(k).lower()
                            if '20 hour' in key_l:
                                if v is not None:
                                    percent_val = int(float(v))
                                    break
                        if percent_val is not None:
                            data['players_20h_plus'] = percent_val
                            logging.info(f"Found players_20h_plus: {percent_val}")
                    except Exception:
                        pass
                else:
                    logging.warning("Failed to get Playtime Breakdown")
                    
            except Exception as e:
                logging.warning(f"Failed to get Playtime Breakdown: {str(e)}")
            
            # Extract Average and Median time played as strings
            try:
                avg_selector_candidates = [
                    "//td[b[contains(text(), 'Average time played')]]/following-sibling::td",
                    "//tr[td/b[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'average time played')]]/td[2]"
                ]
                for selector in avg_selector_candidates:
                    try:
                        el = self.driver.find_element(By.XPATH, selector)
                        text_val = el.text.strip()
                        if text_val:
                            data['avg_playtime'] = text_val
                            logging.info(f"Found Average Time Played: {text_val}")
                            break
                    except:
                        continue
            except Exception as e:
                logging.warning(f"Failed to get Average Time Played: {str(e)}")
            
            try:
                median_selector_candidates = [
                    "//td[b[contains(text(), 'Median time played')]]/following-sibling::td",
                    "//tr[td/b[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'median time played')]]/td[2]"
                ]
                for selector in median_selector_candidates:
                    try:
                        el = self.driver.find_element(By.XPATH, selector)
                        text_val = el.text.strip()
                        if text_val:
                            data['median_playtime'] = text_val
                            logging.info(f"Found Median Time Played (Playtime page): {text_val}")
                            break
                    except:
                        continue
            except Exception as e:
                logging.warning(f"Failed to get Median Time Played (Playtime page): {str(e)}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting data from Lifetime Play Time Page: {str(e)}")
            return None
    
    def extract_wishlist_page_data(self):
        """Extract data from the Wishlist Page"""
        url = f"https://partner.steampowered.com/app/wishlist/{self.steam_app_id}/"
        
        if not self.navigate_to_page(url, "Wishlist Page"):
            return None
        
        
        
        data = {}
        
        try:
            # Set time filter to yesterday
            self.set_yesterday_filter()
            
            # Extract Wishlist daily stats from "Wishlist Action Summary, yesterday" table
            logging.info("Extracting Wishlist Statistics (daily table)...")
            try:
                stats_table_rows = self.driver.find_elements(
                    By.XPATH,
                    "//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'wishlist action summary')]/following::table[1]//tr[td]"
                )
                additions = deletions = conversions = None
                for row in stats_table_rows:
                    try:
                        tds = row.find_elements(By.XPATH, ".//td")
                        if len(tds) < 3:
                            continue
                        label = (tds[0].text or '').strip().lower()
                        # Yesterday value appears in the 3rd cell in sample
                        val_txt = tds[2].text.strip()
                        if not val_txt:
                            continue
                        val_num = self.parse_numeric_value(val_txt)
                        if val_num is None:
                            continue
                        if 'wishlist additions' in label:
                            additions = int(val_num)
                        elif 'wishlist deletions' in label:
                            deletions = int(val_num)
                        elif 'wishlist purchases' in label and 'activations' in label:
                            conversions = int(val_num)
                    except Exception:
                        continue
                if additions is not None:
                    data['wishlist_additions'] = additions
                    logging.info(f"Found Wishlist Additions (daily): {additions}")
                if deletions is not None:
                    data['wishlist_deletions'] = deletions
                    logging.info(f"Found Wishlist Deletions (daily): {deletions}")
                if conversions is not None:
                    data['wishlist_conversions'] = conversions
                    logging.info(f"Found Wishlist Purchases & Activations (daily): {conversions}")
                if additions is None and deletions is None and conversions is None:
                    logging.warning("Could not find daily Wishlist Action Summary values")
            except Exception as e:
                logging.warning(f"Failed to get daily Wishlist Stats: {str(e)}")
            
            # Extract Lifetime Wishlist Conversion Rate
            logging.info("Extracting Lifetime Wishlist Conversion Rate...")
            try:
                rate_selectors = [
                    "//td[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lifetime') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'conversion')]/following-sibling::td",
                    "//td[contains(text(), 'Lifetime Conversion Rate')]/following-sibling::td"
                ]
                for selector in rate_selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element.text.strip():
                            rate_val = self.parse_numeric_value(element.text)
                            if rate_val is not None:
                                data['lifetime_wishlist_conversion_rate'] = rate_val
                                logging.info(f"Found Lifetime Wishlist Conversion Rate: {rate_val}")
                                break
                    except:
                        continue
            except Exception as e:
                logging.warning(f"Failed to get Lifetime Wishlist Conversion Rate: {str(e)}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting data from Wishlist Page: {str(e)}")
            return None
    
    def extract_players_page_data(self):
        """Extract data from the Players Page"""
        url = f"https://partner.steampowered.com/app/players/{self.steam_app_id}/"
        
        if not self.navigate_to_page(url, "Players Page"):
            return None
        
        
        
        data = {}
        
        try:
            # Set time filter to yesterday
            self.set_yesterday_filter()
            
            # Extract Maximum Daily Active Users
            logging.info("Extracting Maximum Daily Active Users...")
            try:
                dau_selectors = [
                    "//td[contains(text(), 'Maximum daily active users')]/following-sibling::td[@align='right']",
                    "//td[contains(text(), 'Maximum daily active users')]/following-sibling::td[3]",
                    "//td[contains(text(), 'Daily Active Users')]/following-sibling::td"
                ]
                
                dau = None
                for selector in dau_selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element.text.strip():
                            dau = self.parse_numeric_value(element.text)
                            if dau:
                                data['dau'] = dau
                                logging.info(f"Found Daily Active Users: {dau}")
                                break
                    except:
                        continue
                
                if not dau:
                    logging.warning("Failed to get Daily Active Users")
                    
            except Exception as e:
                logging.warning(f"Failed to get Daily Active Users: {str(e)}")
            
            # Extract Maximum Daily Peak Concurrent Users
            logging.info("Extracting Maximum Daily Peak Concurrent Users...")
            try:
                pcu_selectors = [
                    "//td[contains(text(), 'Maximum daily peak concurrent users')]/following-sibling::td[@align='right']",
                    "//td[contains(text(), 'Maximum daily peak concurrent users')]/following-sibling::td[3]",
                    "//td[contains(text(), 'Peak Concurrent Users')]/following-sibling::td"
                ]
                
                pcu = None
                for selector in pcu_selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element.text.strip():
                            pcu = self.parse_numeric_value(element.text)
                            if pcu:
                                data['pcu'] = pcu
                                logging.info(f"Found Peak Concurrent Users: {pcu}")
                                break
                    except:
                        continue
                
                if not pcu:
                    logging.warning("Failed to get Peak Concurrent Users")
                    
            except Exception as e:
                logging.warning(f"Failed to get Peak Concurrent Users: {str(e)}")
            
            # Extract Top 10 countries by % of players
            try:
                # Locate the table with headers Country and % of Players
                country_table_xpath = (
                    "//table[.//td/b[normalize-space()='Country'] and .//td/b[contains(., '% of Players')]]"
                )
                tables = self.driver.find_elements(By.XPATH, country_table_xpath)
                top_list = []
                if tables:
                    rows = tables[0].find_elements(By.XPATH, ".//tr[td]")
                    for row in rows:
                        cells = row.find_elements(By.XPATH, ".//td")
                        if len(cells) < 2:
                            continue
                        # Skip header row
                        header_text = (cells[0].text or '').strip().lower()
                        if header_text == 'country':
                            continue
                        # Extract country and percent
                        country_text = cells[0].text.strip()
                        # If there's a link, its text is the country name
                        try:
                            link = cells[0].find_element(By.XPATH, ".//a")
                            if link.text.strip():
                                country_text = link.text.strip()
                        except Exception:
                            pass
                        share_text = cells[1].text.strip()
                        if not country_text or not share_text:
                            continue
                        # Parse percent; keep string formatted to 2 decimals with %
                        share_val = self.parse_numeric_value(share_text)
                        if share_val is None:
                            continue
                        share_pct_str = f"{float(share_val):.2f}%"
                        entry = {
                            'country': country_text,
                            'share': share_pct_str,
                        }
                        # Rank based on order encountered
                        top_list.append(entry)
                        if len(top_list) >= 10:
                            break
                if top_list:
                    # Add rank and players if dau known
                    dau_val = data.get('dau')
                    for idx, item in enumerate(top_list, start=1):
                        item['rank'] = idx
                        if dau_val is not None:
                            try:
                                pct_num = float(item['share'].replace('%', '')) / 100.0
                                item['players'] = int(round(float(dau_val) * pct_num))
                            except Exception:
                                pass
                    data['top10_country_dau'] = top_list
                    logging.info(f"Extracted top10_country_dau with {len(top_list)} entries")
                else:
                    logging.warning("Failed to extract top10_country_dau")
            except Exception as e:
                logging.warning(f"Error extracting top10_country_dau: {str(e)}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting data from Players Page: {str(e)}")
            return None
    
    def extract_regions_revenue_page_data(self):
        """Extract data from the Regions and Countries Revenue Page"""
        url = f"https://partner.steampowered.com/region/?&appID={self.steam_app_id}"
        
        if not self.navigate_to_page(url, "Regions and Countries Revenue Page"):
            return None
        
        data = {}
        
        try:
            # Set time filter to yesterday
            self.set_yesterday_filter()

            # Extract World table daily revenue and daily units
            try:
                # Find the header row for World section
                header_world = self.driver.find_elements(By.XPATH, "//th[normalize-space()='World']/ancestor::tr")
                if header_world:
                    rows = header_world[0].find_elements(By.XPATH, "following-sibling::tr")
                    daily_units_val = None
                    daily_rev_val = None
                    for row in rows:
                        ths = row.find_elements(By.XPATH, ".//th")
                        if ths:
                            # Stop when we reach next section
                            break
                        tds = row.find_elements(By.XPATH, ".//td")
                        if len(tds) < 9:
                            continue
                        label = (tds[3].text or '').strip().lower()
                        if label == 'revenue' and daily_rev_val is None:
                            r = self.parse_numeric_value(tds[4].text.strip())
                            if r is not None:
                                try:
                                    daily_rev_val = float(r)
                                except Exception:
                                    pass
                        if label == 'units':
                            val = self.parse_numeric_value(tds[4].text.strip())
                            if val is None:
                                val = 0
                            try:
                                daily_units_val = int(val)
                            except Exception:
                                daily_units_val = 0
                    if daily_rev_val is not None:
                        data['daily_total_revenue'] = daily_rev_val
                        logging.info(f"Extracted World daily revenue: {daily_rev_val}")
                    if daily_units_val is not None:
                        data['daily_units'] = daily_units_val
                        logging.info(f"Extracted World daily units: {daily_units_val}")
                else:
                    logging.warning("World header not found for daily units")
            except Exception as e:
                logging.warning(f"Error extracting World daily units: {str(e)}")
            
            # Extract Top 10 Regions by revenue (parse rows under 'Regions' header)
            try:
                header_regions = self.driver.find_elements(By.XPATH, "//th[normalize-space()='Regions']/ancestor::tr")
                if header_regions:
                    rows = header_regions[0].find_elements(By.XPATH, "following-sibling::tr")
                    region_to_metrics = {}
                    region_current_name = None
                    for row in rows:
                        # stop when we reach the Countries header
                        ths = row.find_elements(By.XPATH, ".//th")
                        if ths:
                            txt = (ths[0].text or '').strip()
                            if txt.lower() == 'countries':
                                break
                        tds = row.find_elements(By.XPATH, ".//td")
                        if len(tds) < 9:
                            continue
                        try:
                            label = (tds[3].text or '').strip().lower()
                            name_cell = tds[1]
                            name = name_cell.text.strip()
                            try:
                                link = name_cell.find_element(By.XPATH, ".//a")
                                if link.text.strip():
                                    name = link.text.strip()
                            except Exception:
                                pass
                            # When on a units row, name cell may be empty; fallback to last revenue name
                            if not name and 'unit' in label and region_current_name:
                                name = region_current_name
                            if not name:
                                continue
                            entry = region_to_metrics.get(name, {'region': name})
                            # Share column applies for both rows
                            share_raw = tds[2].text.strip() or tds[2].get_attribute('innerText') or ''
                            share_val = self.parse_numeric_value(share_raw)
                            if share_val is not None:
                                entry['share'] = f"{float(share_val):.2f}%"
                            # Change column is on revenue row
                            if label == 'revenue':
                                revenue_val = self.parse_numeric_value(tds[4].text.strip())
                                entry['revenue'] = float(revenue_val) if revenue_val is not None else None
                                change_raw = tds[6].text.strip()
                                change_num = self.parse_numeric_value(change_raw)
                                sign = '-' if '-' in change_raw else '+' if '+' in change_raw else ''
                                entry['change_vs_prior'] = f"{sign}{abs(float(change_num)):.2f}%" if change_num is not None else "0.00%"
                                # remember the last seen name from a revenue row
                                region_current_name = name
                            elif 'unit' in label:
                                units_val = self.parse_numeric_value(tds[4].text.strip())
                                try:
                                    entry['units'] = int(units_val) if units_val is not None else 0
                                except Exception:
                                    entry['units'] = 0
                            region_to_metrics[name] = entry
                        except Exception:
                            continue
                    # Build list limited to top 10 by revenue
                    region_entries = [
                        {**v} for v in region_to_metrics.values()
                        if isinstance(v.get('revenue'), (int, float))
                    ]
                    region_entries.sort(key=lambda x: x.get('revenue', 0), reverse=True)
                    top_regions = region_entries[:10]
                    for i, item in enumerate(top_regions, start=1):
                        item['rank'] = i
                        if 'units' not in item or not isinstance(item.get('units'), int):
                            item['units'] = 0
                    if top_regions:
                        data['top10_region_revenue'] = top_regions
                        logging.info(f"Extracted top10_region_revenue with {len(top_regions)} entries")
                    else:
                        logging.warning("Failed to extract top10_region_revenue")
                else:
                    logging.warning("Regions header not found")
            except Exception as e:
                logging.warning(f"Error extracting top10_region_revenue: {str(e)}")

            # Extract Top 10 Countries by revenue (parse rows under 'Countries' header)
            try:
                header_countries = self.driver.find_elements(By.XPATH, "//th[normalize-space()='Countries']/ancestor::tr")
                if header_countries:
                    rows = header_countries[0].find_elements(By.XPATH, "following-sibling::tr")
                    country_to_metrics = {}
                    country_current_name = None
                    for row in rows:
                        # stop when the next section begins (another th) or table end
                        ths = row.find_elements(By.XPATH, ".//th")
                        if ths:
                            break
                        tds = row.find_elements(By.XPATH, ".//td")
                        if len(tds) < 9:
                            continue
                        try:
                            label = (tds[3].text or '').strip().lower()
                            name_cell = tds[1]
                            name = name_cell.text.strip()
                            try:
                                link = name_cell.find_element(By.XPATH, ".//a")
                                if link.text.strip():
                                    name = link.text.strip()
                            except Exception:
                                pass
                            # units rows may not repeat the name; fallback to last revenue name
                            if not name and 'unit' in label and country_current_name:
                                name = country_current_name
                            if not name:
                                continue
                            entry = country_to_metrics.get(name, {'country': name})
                            share_raw = tds[2].text.strip() or tds[2].get_attribute('innerText') or ''
                            share_val = self.parse_numeric_value(share_raw)
                            if share_val is not None:
                                entry['share'] = f"{float(share_val):.2f}%"
                            if label == 'revenue':
                                revenue_val = self.parse_numeric_value(tds[4].text.strip())
                                entry['revenue'] = float(revenue_val) if revenue_val is not None else None
                                change_raw = tds[6].text.strip()
                                change_num = self.parse_numeric_value(change_raw)
                                sign = '-' if '-' in change_raw else '+' if '+' in change_raw else ''
                                entry['change_vs_prior'] = f"{sign}{abs(float(change_num)):.2f}%" if change_num is not None else "0.00%"
                                # remember last revenue-name for units rows
                                country_current_name = name
                            elif 'unit' in label:
                                units_val = self.parse_numeric_value(tds[4].text.strip())
                                try:
                                    entry['units'] = int(units_val) if units_val is not None else 0
                                except Exception:
                                    entry['units'] = 0
                            country_to_metrics[name] = entry
                        except Exception:
                            continue
                    # Build list limited to top 10 by revenue
                    country_entries = [
                        {**v} for v in country_to_metrics.values()
                        if isinstance(v.get('revenue'), (int, float))
                    ]
                    country_entries.sort(key=lambda x: x.get('revenue', 0), reverse=True)
                    top_countries = country_entries[:10]
                    for i, item in enumerate(top_countries, start=1):
                        item['rank'] = i
                        if 'units' not in item or not isinstance(item.get('units'), int):
                            item['units'] = 0
                    if top_countries:
                        data['top10_country_revenue'] = top_countries
                        logging.info(f"Extracted top10_country_revenue with {len(top_countries)} entries")
                    else:
                        logging.warning("Failed to extract top10_country_revenue")
                else:
                    logging.warning("Countries header not found")
            except Exception as e:
                logging.warning(f"Error extracting top10_country_revenue: {str(e)}")

            return data
            
        except Exception as e:
            logging.error(f"Error extracting data from Regions Revenue Page: {str(e)}")
            return None
    
    def extract_downloads_region_page_data(self):
        """Extract data from the Downloads by Region Page"""
        url = f"https://partner.steampowered.com/nav_regions.php?downloads=1&appID={self.steam_app_id}"
        
        if not self.navigate_to_page(url, "Downloads by Region Page"):
            return None
        
        data = {}
        
        try:
            # Set time filter to yesterday
            self.set_yesterday_filter()
            

            
            # Extract Total Downloads
            logging.info("Extracting Total Downloads...")
            try:
                total_downloads_selectors = [
                    "//div[contains(text(), 'Total Downloads:')]",
                    "//td[contains(text(), 'Total Downloads')]/following-sibling::td",
                    "//div[contains(text(), 'Total Downloads')]/following-sibling::*",
                    "//span[contains(text(), 'Total Downloads')]/following-sibling::*"
                ]
                
                total_downloads = None
                for selector in total_downloads_selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element.text.strip():
                            # Handle "Total Downloads: 52,475" format
                            text = element.text.strip()
                            if "Total Downloads:" in text:
                                # Extract the number after the colon
                                parts = text.split(":")
                                if len(parts) > 1:
                                    total_downloads = self.parse_numeric_value(parts[1].strip())
                                else:
                                    total_downloads = self.parse_numeric_value(text)
                            else:
                                total_downloads = self.parse_numeric_value(text)
                            
                            if total_downloads:
                                data['total_downloads'] = total_downloads
                                logging.info(f"Found Total Downloads: {total_downloads}")
                                break
                    except:
                        continue
                
                if not total_downloads:
                    logging.warning("Failed to get Total Downloads")
                    
            except Exception as e:
                logging.warning(f"Failed to get Total Downloads: {str(e)}")
            
            # Extract top 10 regions by downloads
            try:
                region_table_xpath = "//table[.//td/b[normalize-space()='Region'] and .//td/b[normalize-space()='Total downloads'] and .//td/b[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='share']]"
                tables = self.driver.find_elements(By.XPATH, region_table_xpath)
                if tables:
                    rows = tables[0].find_elements(By.XPATH, ".//tr[td]")
                    region_list = []
                    for row in rows:
                        cells = row.find_elements(By.XPATH, ".//td")
                        if len(cells) < 3:
                            continue
                        # Skip header
                        if (cells[0].text or '').strip().lower() == 'region':
                            continue
                        region_name = cells[0].text.strip()
                        try:
                            link = cells[0].find_element(By.XPATH, ".//a")
                            if link.text.strip():
                                region_name = link.text.strip()
                        except Exception:
                            pass
                        downloads_text = cells[1].text.strip()
                        share_text = cells[2].text.strip()
                        if not region_name or not downloads_text or not share_text:
                            continue
                        downloads_val = self.parse_numeric_value(downloads_text)
                        share_val = self.parse_numeric_value(share_text)
                        if downloads_val is None or share_val is None:
                            continue
                        region_list.append({
                            'region': region_name,
                            'downloads': int(downloads_val),
                            'share': f"{float(share_val):.2f}%",
                        })
                        if len(region_list) >= 10:
                            break
                    if region_list:
                        for idx, item in enumerate(region_list, start=1):
                            item['rank'] = idx
                        data['top10_region_downloads'] = region_list
                        logging.info(f"Extracted top10_region_downloads with {len(region_list)} entries")
                    else:
                        logging.warning("Failed to extract top10_region_downloads")
            except Exception as e:
                logging.warning(f"Error extracting top10_region_downloads: {str(e)}")

            # Extract top 10 countries by downloads
            try:
                country_table_xpath = "//table[.//td/b[normalize-space()='Country'] and .//td/b[normalize-space()='Total downloads'] and .//td/b[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='share']]"
                tables = self.driver.find_elements(By.XPATH, country_table_xpath)
                if tables:
                    rows = tables[0].find_elements(By.XPATH, ".//tr[td]")
                    country_list = []
                    for row in rows:
                        cells = row.find_elements(By.XPATH, ".//td")
                        if len(cells) < 3:
                            continue
                        # Skip header
                        if (cells[0].text or '').strip().lower() == 'country':
                            continue
                        country_name = cells[0].text.strip()
                        try:
                            link = cells[0].find_element(By.XPATH, ".//a")
                            if link.text.strip():
                                country_name = link.text.strip()
                        except Exception:
                            pass
                        downloads_text = cells[1].text.strip()
                        share_text = cells[2].text.strip()
                        if not country_name or not downloads_text or not share_text:
                            continue
                        downloads_val = self.parse_numeric_value(downloads_text)
                        share_val = self.parse_numeric_value(share_text)
                        if downloads_val is None or share_val is None:
                            continue
                        country_list.append({
                            'country': country_name,
                            'downloads': int(downloads_val),
                            'share': f"{float(share_val):.2f}%",
                        })
                        if len(country_list) >= 10:
                            break
                    if country_list:
                        for idx, item in enumerate(country_list, start=1):
                            item['rank'] = idx
                        data['top10_country_downloads'] = country_list
                        logging.info(f"Extracted top10_country_downloads with {len(country_list)} entries")
                    else:
                        logging.warning("Failed to extract top10_country_downloads")
            except Exception as e:
                logging.warning(f"Error extracting top10_country_downloads: {str(e)}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting data from Downloads Region Page: {str(e)}")
            return None
    
    def extract_in_game_purchases_page_data(self):
        """Extract data from the In-Game Purchases Page"""
        url = f"https://partner.steampowered.com/app/microtxn/{self.steam_app_id}/"
        
        if not self.navigate_to_page(url, "In-Game Purchases Page"):
            return None
        
        data = {}
        
        try:
            # Set time filter to yesterday
            self.set_yesterday_filter()
            

            
            # Do not fetch daily_total_revenue here; it is sourced from Regions World section
            
            # Do not fetch lifetime_total_revenue here; it is sourced from Detail page
            
            # Extract IAP breakdown table (Item, ID, Units, Average Price, Revenue)
            try:
                breakdown_rows = []
                # Target the Item Breakdown table by its header context
                tables = self.driver.find_elements(By.XPATH, "//h2[contains(., 'Item Breakdown')]/following::table[1]//tr[td]")
                for row in tables:
                    try:
                        tds = row.find_elements(By.XPATH, ".//td")
                        if len(tds) < 6:
                            continue
                        # Skip header rows (contain th elsewhere or bold labels)
                        # Identify by checking if the first cell has a link (item name) and ID is numeric
                        item_name = tds[0].text.strip()
                        try:
                            link = tds[0].find_element(By.XPATH, ".//a")
                            if link.text.strip():
                                item_name = link.text.strip()
                        except Exception:
                            pass
                        item_id = tds[1].text.strip()
                        units_txt = tds[3].text.strip()
                        avg_price_txt = tds[4].text.strip()
                        revenue_txt = tds[5].text.strip()
                        # Basic validation
                        if not item_name or not item_id:
                            continue
                        units_val = self.parse_numeric_value(units_txt)
                        avg_price_val = self.parse_numeric_value(avg_price_txt)
                        revenue_val = self.parse_numeric_value(revenue_txt)
                        if units_val is None or avg_price_val is None or revenue_val is None:
                            continue
                        breakdown_rows.append({
                            'item': item_name,
                            'id': str(item_id),
                            'units': int(units_val),
                            'average_price': round(float(avg_price_val), 2),
                            'revenue': round(float(revenue_val), 2),
                        })
                    except Exception:
                        continue
                if breakdown_rows:
                    # Rank by revenue desc
                    breakdown_rows.sort(key=lambda x: x['revenue'], reverse=True)
                    for idx, entry in enumerate(breakdown_rows, start=1):
                        entry['rank'] = idx
                    data['iap_breakdown_json'] = breakdown_rows
                    # Compute top3_iap_share
                    total_rev = sum(e['revenue'] for e in breakdown_rows)
                    if total_rev > 0:
                        top3_rev = sum(e['revenue'] for e in breakdown_rows[:3])
                        data['top3_iap_share'] = round(top3_rev / total_rev, 4)
                else:
                    logging.warning("IAP breakdown table not found or empty")
            except Exception as e:
                logging.warning(f"Failed to parse IAP breakdown: {str(e)}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting data from In-Game Purchases Page: {str(e)}")
            return None
    
    def parse_numeric_value(self, text):
        """Parse numeric values from text, handling different formats"""
        if not text:
            return None
        
        # Remove common non-numeric characters
        cleaned = text.replace(',', '').replace('$', '').replace('%', '').replace('(', '').replace(')', '').strip()
        
        # Handle time format (e.g., "32 minutes" -> 32)
        if 'minutes' in cleaned.lower():
            cleaned = cleaned.replace('minutes', '').strip()
        
        try:
            # Try to parse as float first
            return float(cleaned)
        except ValueError:
            try:
                # Try to parse as integer
                return int(cleaned)
            except ValueError:
                # Return None if can't parse
                return None
    
    def get_game_table_name(self):
        """Get the game-specific table name based on steam_app_id"""
        game_tables = {
            2507950: 'delta_force_daily_metrics',
            3104410: 'terminull_brigade_daily_metrics', 
            3478050: 'road_to_empress_daily_metrics',
            2073620: 'arena_breakout_infinite_daily_metrics'
        }
        return game_tables.get(self.steam_app_id)

    def save_to_database(self, data):
        """Save extracted data to both main table and game-specific table"""
        if not data:
            logging.warning("No data to save")
            return False
        
        connection = None
        cursor = None
        
        try:
            logging.info("Connecting to database...")
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor()
            
            # Compute stat_date as Pacific yesterday
            if ZoneInfo:
                now_pt = datetime.now(ZoneInfo('America/Los_Angeles'))
                stat_date = (now_pt - timedelta(days=1)).date()
            else:
                # Fallback to system local time minus one day
                stat_date = (datetime.now() - timedelta(days=1)).date()
            
            # Compute new_players from yesterday's unique_player (same steam_app_id)
            new_players_val = None
            unique_today = data.get('unique_player')
            if unique_today is not None:
                try:
                    prev_date = stat_date - timedelta(days=1)
                    cursor_prev = connection.cursor()
                    cursor_prev.execute(
                        "SELECT unique_player FROM game_daily_metrics WHERE steam_app_id=%s AND stat_date=%s",
                        (int(self.steam_app_id), prev_date)
                    )
                    prev_row = cursor_prev.fetchone()
                    if prev_row is None:
                        # First run: use today's unique_player
                        new_players_val = int(unique_today)
                    else:
                        prev_unique = prev_row[0]
                        if prev_unique is None:
                            new_players_val = None
                        else:
                            delta = int(unique_today) - int(prev_unique)
                            new_players_val = delta if delta >= 0 else 0
                except Exception:
                    new_players_val = None
                finally:
                    try:
                        cursor_prev.close()
                    except Exception:
                        pass

            # Compute d1_retention = (today_dau - today_new_players) / yesterday_dau
            d1_retention_val = None
            try:
                today_dau = data.get('dau')
                if today_dau is not None and new_players_val is not None:
                    prev_date = stat_date - timedelta(days=1)
                    cursor_prev_dau = connection.cursor()
                    cursor_prev_dau.execute(
                        "SELECT dau FROM game_daily_metrics WHERE steam_app_id=%s AND stat_date=%s",
                        (int(self.steam_app_id), prev_date)
                    )
                    row = cursor_prev_dau.fetchone()
                    if row is not None and row[0] is not None and float(row[0]) > 0:
                        numerator = float(today_dau) - float(new_players_val)
                        denom = float(row[0])
                        if denom > 0:
                            d1_retention_val = round(numerator / denom, 2)
            except Exception:
                d1_retention_val = None
            finally:
                try:
                    cursor_prev_dau.close()
                except Exception:
                    pass

            # Compute new_vs_returning_ratio = new_players / (dau - new_players)
            new_vs_returning_ratio_val = None
            try:
                today_dau = data.get('dau')
                if today_dau is not None and new_players_val is not None:
                    returning = float(today_dau) - float(new_players_val)
                    if returning > 0:
                        new_vs_returning_ratio_val = round(float(new_players_val) / returning, 2)
            except Exception:
                new_vs_returning_ratio_val = None

            # Compute pcu_over_dau (rounded to 2 decimals) if possible
            pcu_over_dau_val = None
            try:
                dau_val = data.get('dau')
                pcu_val = data.get('pcu')
                if dau_val is not None and pcu_val is not None and float(dau_val) > 0:
                    pcu_over_dau_val = round(float(pcu_val) / float(dau_val), 2)
            except Exception:
                pcu_over_dau_val = None

            # Compute daily_arpu = daily_total_revenue / dau (round to 6 decimals per schema)
            daily_arpu_val = None
            try:
                revenue_val = data.get('daily_total_revenue')
                dau_val = data.get('dau')
                if revenue_val is not None and dau_val is not None and float(dau_val) > 0:
                    daily_arpu_val = round(float(revenue_val) / float(dau_val), 2)
            except Exception:
                daily_arpu_val = None

            # Enrich top10_country_revenue with ARPU using players from top10_country_dau
            try:
                country_dau_list = data.get('top10_country_dau')
                country_rev_list = data.get('top10_country_revenue')
                if isinstance(country_dau_list, list) and isinstance(country_rev_list, list):
                    # Build map: country -> players
                    players_map = {}
                    for entry in country_dau_list:
                        try:
                            country_name = (entry.get('country') or '').strip()
                            players_val = entry.get('players')
                            if country_name and isinstance(players_val, (int, float)) and float(players_val) > 0:
                                players_map[country_name] = int(round(float(players_val)))
                        except Exception:
                            continue
                    # Inject ARPU in revenue list when possible
                    enriched = []
                    for entry in country_rev_list:
                        try:
                            country_name = (entry.get('country') or '').strip()
                            revenue_val = entry.get('revenue')
                            if country_name and isinstance(revenue_val, (int, float)) and country_name in players_map:
                                players_val = players_map[country_name]
                                if players_val > 0:
                                    arpu_val = round(float(revenue_val) / float(players_val), 2)
                                    new_entry = dict(entry)
                                    new_entry['arpu'] = arpu_val
                                    enriched.append(new_entry)
                                    continue
                            # If cannot compute, keep entry as-is
                            enriched.append(entry)
                        except Exception:
                            enriched.append(entry)
                    data['top10_country_revenue'] = enriched
            except Exception:
                pass

            # Prepare insert payload (same for both tables)
            insert_payload = {
                'steam_app_id': int(self.steam_app_id),
                'game_name': self.game_name,
                'stat_date': stat_date,
                # Direct fields if present
                'unique_player': data.get('unique_player'),
                'lifetime_total_units': data.get('lifetime_total_units'),
                'new_players': new_players_val,
                'wishlist': data.get('wishlist'),
                'dau': data.get('dau'),
                'pcu': data.get('pcu'),
                'pcu_over_dau': pcu_over_dau_val,
                'players_20h_plus': data.get('players_20h_plus'),
                'd1_retention': d1_retention_val,
                'new_vs_returning_ratio': new_vs_returning_ratio_val,
                'total_downloads': data.get('total_downloads'),
                'daily_total_revenue': data.get('daily_total_revenue'),
                'daily_units': data.get('daily_units'),
                'daily_arpu': daily_arpu_val,
                'lifetime_total_revenue': data.get('lifetime_total_revenue'),
                'top10_country_dau': json.dumps(data.get('top10_country_dau')) if data.get('top10_country_dau') is not None else None,
                'top10_country_downloads': json.dumps(data.get('top10_country_downloads')) if data.get('top10_country_downloads') is not None else None,
                'top10_region_downloads': json.dumps(data.get('top10_region_downloads')) if data.get('top10_region_downloads') is not None else None,
                'top10_country_revenue': json.dumps(data.get('top10_country_revenue')) if data.get('top10_country_revenue') is not None else None,
                'top10_region_revenue': json.dumps(data.get('top10_region_revenue')) if data.get('top10_region_revenue') is not None else None,
                'iap_breakdown_json': json.dumps(data.get('iap_breakdown_json')) if data.get('iap_breakdown_json') is not None else None,
                'top3_iap_share': data.get('top3_iap_share'),
                'wishlist_additions': data.get('wishlist_additions'),
                'wishlist_deletions': data.get('wishlist_deletions'),
                'wishlist_conversions': data.get('wishlist_conversions'),
                'lifetime_wishlist_conversion_rate': data.get('lifetime_wishlist_conversion_rate'),
                'median_playtime': data.get('median_playtime'),
                'avg_playtime': data.get('avg_playtime'),
            }
            # Remove None values to build dynamic column list
            insert_payload = {k: v for k, v in insert_payload.items() if v is not None}
            
            columns = list(insert_payload.keys())
            placeholders = ', '.join([f'%({col})s' for col in columns])
            column_names = ', '.join(columns)
            
            # Save to main table (game_daily_metrics)
            main_insert_query = f"""
            INSERT INTO game_daily_metrics ({column_names})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
            """
            
            # Add update clauses for main table (exclude PK columns)
            main_update_clauses = []
            for col in columns:
                if col not in ('stat_date', 'steam_app_id'):  # Do not update PK
                    main_update_clauses.append(f"{col} = VALUES({col})")
            
            main_insert_query += ', '.join(main_update_clauses)
            
            logging.info("Saving data to main table (game_daily_metrics)...")
            cursor.execute(main_insert_query, insert_payload)
            
            # Save to game-specific table
            game_table_name = self.get_game_table_name()
            if game_table_name:
                # For game-specific table, exclude steam_app_id from PK update clauses
                game_insert_query = f"""
                INSERT INTO {game_table_name} ({column_names})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE
                """
                
                # Add update clauses for game table (exclude stat_date from updates)
                game_update_clauses = []
                for col in columns:
                    if col != 'stat_date':  # Only exclude stat_date (PK for game tables)
                        game_update_clauses.append(f"{col} = VALUES({col})")
                
                game_insert_query += ', '.join(game_update_clauses)
                
                logging.info(f"Saving data to game-specific table ({game_table_name})...")
                cursor.execute(game_insert_query, insert_payload)
            else:
                logging.warning(f"No game-specific table found for steam_app_id: {self.steam_app_id}")
            
            connection.commit()
            
            logging.info(f"Data saved to database successfully (main table + game-specific table)")
            return True
            
        except Error as e:
            logging.error(f"Database error: {e}")
            return False
        except Exception as e:
            logging.error(f"Error saving to database: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
    
    def run_crawler(self):
        """Main crawler execution method"""
        start_time = time.time()
        
        try:
            logging.info("Starting SteamWorks crawler...")
            
            # Setup Chrome driver
            self.setup_driver()
            # Warmup: open SteamWorks home once to ensure proper session
            self.warmup_session()
            # Ensure we are viewing as the target partner account
            self.ensure_partner_context()
            
            # Initialize combined data
            all_data = {}
            
            # Extract data from Default Game Page
            logging.info("=== Extracting from Default Game Page ===")
            default_data = self.extract_default_page_data()
            if default_data:
                all_data.update(default_data)
            
            # Extract data from Lifetime Play Time Page
            logging.info("=== Extracting from Lifetime Play Time Page ===")
            playtime_data = self.extract_playtime_page_data()
            if playtime_data:
                all_data.update(playtime_data)
            
            # Extract data from Wishlist Page
            logging.info("=== Extracting from Wishlist Page ===")
            wishlist_data = self.extract_wishlist_page_data()
            if wishlist_data:
                all_data.update(wishlist_data)
            
            # Extract data from Players Page
            logging.info("=== Extracting from Players Page ===")
            players_data = self.extract_players_page_data()
            if players_data:
                all_data.update(players_data)
            
            # Extract data from Regions and Countries Revenue Page
            logging.info("=== Extracting from Regions Revenue Page ===")
            regions_revenue_data = self.extract_regions_revenue_page_data()
            if regions_revenue_data:
                all_data.update(regions_revenue_data)
            
            # Extract data from Downloads by Region Page
            logging.info("=== Extracting from Downloads Region Page ===")
            downloads_region_data = self.extract_downloads_region_page_data()
            if downloads_region_data:
                all_data.update(downloads_region_data)
            
            # Extract data from In-Game Purchases Page
            logging.info("=== Extracting from In-Game Purchases Page ===")
            in_game_purchases_data = self.extract_in_game_purchases_page_data()
            if in_game_purchases_data:
                all_data.update(in_game_purchases_data)
            
            if all_data:
                # Save to database
                success = self.save_to_database(all_data)
                if success:
                    logging.info("Crawler completed successfully")
                    return True, all_data
                else:
                    logging.error("✗ Failed to save data to database")
                    return False, "Database save failed"
            else:
                logging.error("✗ Failed to extract any data")
                return False, "Data extraction failed"
                
        except Exception as e:
            logging.error(f"Crawler execution failed: {str(e)}")
            return False, str(e)
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver closed")

def main():
    """Main function to run the crawler"""
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'database': 'steamworks_crawler',
        'user': 'root',
        'password': 'Zh1149191843!'
    }
    
    # Games to run. You can override via env var STEAMWORKS_GAMES, format:
    # STEAMWORKS_GAMES="2507950:Delta Force,3104410:Terminull Brigade"
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
        # Default games list
        games = [
            (2507950, 'Delta Force'),
            (3104410, 'Terminull Brigade'),
            (3478050, 'Road to Empress'),
            (2073620, 'Arena Breakout: Infinite'),
        ]

    overall_success = True
    for app_id, name in games:
        print(f"\n=== Running crawler for {name} ({app_id}) ===")
        crawler = SteamWorksCrawler(db_config, steam_app_id=app_id, game_name=name)
        success, result = crawler.run_crawler()
        if success:
            print("Crawler completed successfully for this game.")
        else:
            print(f"Crawler failed for {name} ({app_id}): {result}")
            overall_success = False

    if overall_success:
        print("\nAll crawls completed.")
    else:
        print("\nSome crawls failed. See logs for details.")

if __name__ == "__main__":
    main() 