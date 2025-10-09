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

# Import the existing marketing crawler class
from steamworks_marketing_crawler import SteamworksMarketingCrawler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('steamworks_historical_marketing_crawler.log'),
        logging.StreamHandler()
    ]
)

class SteamworksHistoricalMarketingCrawler(SteamworksMarketingCrawler):
    def __init__(self, db_config, steam_app_id, game_name, start_date, end_date):
        super().__init__(db_config, steam_app_id, game_name)
        self.start_date = start_date
        self.end_date = end_date
        
    def extract_homepage_breakdown_from_html(self):
        """Extract homepage breakdown data from HTML source by parsing Home Page expanded section - FIXED VERSION"""
        try:
            # Get the page source
            page_source = self.driver.page_source
            import re
            
            # FIXED: More flexible approach to find Home Page expanded content
            homepage_data = []
            
            # Step 1: Look for Home Page expanded content directly
            # Try multiple patterns to find the expanded content
            expanded_patterns = [
                # Home Page uses featurestatsclass_6
                r'<div class="tr feature_stats featurestatsclass_6"[^>]*>.*?</div>\s*</div>',
                # Alternative pattern
                r'<div[^>]*class="[^"]*feature_stats[^"]*featurestatsclass_6[^"]*"[^>]*>.*?</div>\s*</div>',
                # More flexible pattern
                r'<div[^>]*featurestatsclass_6[^>]*>.*?</div>\s*</div>'
            ]
            
            expanded_matches = []
            for pattern in expanded_patterns:
                matches = re.findall(pattern, page_source, re.DOTALL)
                if matches:
                    expanded_matches = matches
                    logging.info(f"Found {len(expanded_matches)} Home Page expanded rows using pattern: {pattern[:50]}...")
                    break
            
            if not expanded_matches:
                logging.warning("Could not find Home Page expanded content with any pattern")
                
                # DEBUG: Let's see what featurestatsclass_6 elements exist
                debug_pattern = r'<div[^>]*featurestatsclass_6[^>]*>.*?</div>\s*</div>'
                debug_matches = re.findall(debug_pattern, page_source, re.DOTALL)
                logging.info(f"DEBUG: Found {len(debug_matches)} featurestatsclass_6 elements total")
                
                if debug_matches:
                    logging.info("DEBUG: Sample featurestatsclass_6 elements:")
                    for i, match in enumerate(debug_matches[:3]):
                        strong_match = re.search(r'<strong>([^<]+)</strong>', match)
                        if strong_match:
                            logging.info(f"  {i+1}. Title: {strong_match.group(1)}")
                        else:
                            logging.info(f"  {i+1}. No title found")
                
                return []
            
            logging.info(f"Found {len(expanded_matches)} Home Page expanded rows")
            
            # Step 2: Process each expanded row with 1% filter
            for row_html in expanded_matches:
                try:
                    # Extract page/feature name
                    name_pattern = r'<strong>([^<]+)</strong>'
                    name_match = re.search(name_pattern, row_html)
                    if not name_match:
                        continue
                    
                    page_feature = name_match.group(1).strip()
                    
                    # Filter out entries that don't belong in homepage breakdown
                    invalid_entries = ['Image', 'Button', 'Primary Store Link', 'Search Auto-complete', 'Discovery Queue']
                    if page_feature in invalid_entries:
                        continue
                    
                    # Extract all td values
                    td_pattern = r'<div class="td"[^>]*>([^<]*)</div>'
                    all_td_matches = re.findall(td_pattern, row_html)
                    
                    # Filter out the title, keep only data values
                    data_values = []
                    for i, value in enumerate(all_td_matches):
                        clean_value = value.strip()
                        if (clean_value and 
                            clean_value != page_feature and  # Skip the title
                            not clean_value.startswith('expander') and  # Skip expander
                            (clean_value.replace(',', '').replace('.', '').replace('%', '').isdigit() or 
                             '.' in clean_value.replace('%', '') or 
                             ',' in clean_value)):
                            data_values.append(clean_value)
                    
                    # Skip if not enough data values
                    if len(data_values) < 3:
                        continue
                    
                    # Parse the data values to get percentages for filtering
                    field_names = ['impressions', 'owner_impressions', 'percentage_of_total_impressions', 
                                  'click_thru_rate', 'visits', 'owner_visits', 'percentage_of_total_visits']
                    
                    parsed_values = {}
                    for i, value in enumerate(data_values):
                        if i < len(field_names):
                            field_name = field_names[i]
                            
                            if not value.strip():
                                parsed_values[field_name] = 0
                            else:
                                clean_value = value.strip().replace(',', '')
                                if clean_value.endswith('%'):
                                    num_match = re.search(r'([0-9.]+)%?', clean_value)
                                    parsed_values[field_name] = float(num_match.group(1)) if num_match else 0
                                else:
                                    try:
                                        parsed_values[field_name] = int(clean_value)
                                    except ValueError:
                                        parsed_values[field_name] = 0
                    
                    # APPLY 1% FILTER: Skip row if both percentages are <= 1%
                    percentage_impressions = parsed_values.get('percentage_of_total_impressions', 0)
                    percentage_visits = parsed_values.get('percentage_of_total_visits', 0)
                    
                    if percentage_impressions <= 1.0 and percentage_visits <= 1.0:
                        continue  # Skip this row, move to next
                    
                    # Row passed the filter, create the data structure
                    row_data = {
                        'page_feature': page_feature,
                        'impressions': parsed_values.get('impressions', 0),
                        'owner_impressions': parsed_values.get('owner_impressions', 0),
                        'percentage_of_total_impressions': percentage_impressions,
                        'click_thru_rate': parsed_values.get('click_thru_rate', 0),
                        'visits': parsed_values.get('visits', 0),
                        'owner_visits': parsed_values.get('owner_visits', 0),
                        'percentage_of_total_visits': percentage_visits
                    }
                    
                    homepage_data.append(row_data)
                    logging.info(f"Processed Home Page expanded row: {page_feature} with {len(data_values)} values")
                        
                except Exception as e:
                    logging.warning(f"Failed to parse Home Page expanded row: {str(e)}")
                    continue
            
            if homepage_data:
                logging.info(f"Homepage breakdown: extracted {len(homepage_data)} rows (after 1% filter)")
                return homepage_data
            else:
                logging.info("No Home Page expanded rows found after filtering")
                return []
            
        except Exception as e:
            logging.error(f"Failed to extract homepage breakdown from HTML: {str(e)}")
            return []
    
    def extract_all_source_breakdown_from_html(self):
        """Extract all source breakdown data from HTML source by parsing all first-level rows - FIXED VERSION"""
        try:
            # Get the page source
            page_source = self.driver.page_source
            import re
            
            # Look for all first-level rows (highlightHover page_stats)
            first_level_pattern = r'<div class="tr highlightHover page_stats"[^>]*onclick="ToggleFeatureStats[^"]*".*?</div>\s*</div>'
            first_level_matches = re.findall(first_level_pattern, page_source, re.DOTALL)
            
            if not first_level_matches:
                logging.warning("Could not find any first-level rows in HTML source")
                return []
            
            logging.info(f"Found {len(first_level_matches)} first-level rows")
            
            all_source_data = []
            
            # Process each first-level row with 1% filter
            for row_html in first_level_matches:
                try:
                    # Extract page/feature name
                    name_pattern = r'<strong>([^<]+)</strong>'
                    name_match = re.search(name_pattern, row_html)
                    if not name_match:
                        continue
                    
                    page_feature = name_match.group(1).strip()
                    
                    # Extract all td values
                    td_pattern = r'<div class="td"[^>]*>([^<]*)</div>'
                    all_td_matches = re.findall(td_pattern, row_html)
                    
                    # Filter out the title and expander, keep only data values
                    data_values = []
                    for i, value in enumerate(all_td_matches):
                        clean_value = value.strip()
                        if (clean_value and 
                            clean_value != page_feature and  # Skip the title
                            not clean_value.startswith('expander') and  # Skip expander
                            (clean_value.replace(',', '').replace('.', '').replace('%', '').isdigit() or 
                             '.' in clean_value.replace('%', '') or 
                             ',' in clean_value)):
                            data_values.append(clean_value)
                    
                    # Skip if not enough data values
                    if len(data_values) < 3:
                        continue
                    
                    # Parse the data values to get percentages for filtering
                    field_names = ['impressions', 'owner_impressions', 'percentage_of_total_impressions', 
                                  'click_thru_rate', 'visits', 'owner_visits', 'percentage_of_total_visits']
                    
                    parsed_values = {}
                    for i, value in enumerate(data_values):
                        if i < len(field_names):
                            field_name = field_names[i]
                            
                            if not value.strip():
                                parsed_values[field_name] = 0
                            else:
                                clean_value = value.strip().replace(',', '')
                                if clean_value.endswith('%'):
                                    num_match = re.search(r'([0-9.]+)%?', clean_value)
                                    parsed_values[field_name] = float(num_match.group(1)) if num_match else 0
                                else:
                                    try:
                                        parsed_values[field_name] = int(clean_value)
                                    except ValueError:
                                        parsed_values[field_name] = 0
                    
                    # APPLY 1% FILTER: Skip row if both percentages are <= 1%
                    percentage_impressions = parsed_values.get('percentage_of_total_impressions', 0)
                    percentage_visits = parsed_values.get('percentage_of_total_visits', 0)
                    
                    if percentage_impressions <= 1.0 and percentage_visits <= 1.0:
                        continue  # Skip this row, move to next
                    
                    # Row passed the filter, create the data structure
                    row_data = {
                        'page_feature': page_feature,
                        'impressions': parsed_values.get('impressions', 0),
                        'owner_impressions': parsed_values.get('owner_impressions', 0),
                        'percentage_of_total_impressions': percentage_impressions,
                        'click_thru_rate': parsed_values.get('click_thru_rate', 0),
                        'visits': parsed_values.get('visits', 0),
                        'owner_visits': parsed_values.get('owner_visits', 0),
                        'percentage_of_total_visits': percentage_visits
                    }
                    
                    all_source_data.append(row_data)
                    logging.info(f"Processed first-level row: {page_feature} with {len(data_values)} values")
                        
                except Exception as e:
                    logging.warning(f"Failed to parse first-level row: {str(e)}")
                    continue
            
            if all_source_data:
                logging.info(f"All source breakdown: extracted {len(all_source_data)} rows (after 1% filter)")
                return all_source_data
            else:
                logging.info("No valid first-level rows found after filtering")
                return []
            
        except Exception as e:
            logging.error(f"Failed to extract all source breakdown from HTML: {str(e)}")
            return []
    
    def set_custom_date_filter_for_date(self, target_date):
        """Set the time filter to 'Custom' and set both dates to the target_date"""
        try:
            logging.info(f"Setting time filter to 'Custom' for date: {target_date}")
            
            # Format the date as MM/DD/YYYY (US format)
            date_str = target_date.strftime("%m/%d/%Y")
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
            logging.warning(f"Error setting custom date filter: {str(e)}")
            return False
    
    def store_historical_marketing_data(self, data, target_date):
        """Store historical marketing data in game-specific table only"""
        connection = None
        cursor = None
        
        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor()
            
            # Prepare data for insertion
            insert_data = {
                'steam_app_id': self.steam_app_id,
                'game_name': self.game_name,
                'stat_date': target_date,
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
            
            # Insert into game-specific table only
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
                logging.info(f"Inserted historical data into {game_table} for {self.game_name} on {target_date}")
            else:
                logging.error(f"No game-specific table found for steam_app_id: {self.steam_app_id}")
                raise Exception(f"No game-specific table found for steam_app_id: {self.steam_app_id}")
            
            connection.commit()
            logging.info(f"Historical marketing data stored successfully for {target_date}")
            
        except Error as e:
            logging.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Error storing historical marketing data: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
    
    def run_historical_crawler(self):
        """Main execution method for historical data crawling"""
        start_time = time.time()
        
        try:
            logging.info(f"Starting historical marketing crawler for {self.game_name} ({self.steam_app_id})")
            logging.info(f"Date range: {self.start_date} to {self.end_date}")
            
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
            
            # Generate list of dates to process
            current_date = self.start_date
            dates_to_process = []
            while current_date <= self.end_date:
                dates_to_process.append(current_date)
                current_date += timedelta(days=1)
            
            logging.info(f"Will process {len(dates_to_process)} dates")
            
            successful_dates = 0
            failed_dates = 0
            
            # Process each date
            for i, target_date in enumerate(dates_to_process, 1):
                try:
                    logging.info(f"Processing date {i}/{len(dates_to_process)}: {target_date}")
                    
                    # Set custom date filter for this specific date
                    filter_success = self.set_custom_date_filter_for_date(target_date)
                    if not filter_success:
                        logging.warning(f"Could not set custom date filter for {target_date}, skipping")
                        failed_dates += 1
                        continue
                    
                    # Extract basic metrics for this date
                    basic_metrics = self.extract_basic_metrics()
                    
                    if basic_metrics:
                        # Store data for this specific date
                        self.store_historical_marketing_data(basic_metrics, target_date)
                        successful_dates += 1
                        logging.info(f"Successfully processed date {target_date}")
                    else:
                        logging.error(f"Failed to extract data for date {target_date}")
                        failed_dates += 1
                    
                    # Add a small delay between requests to be respectful
                    if i < len(dates_to_process):
                        time.sleep(2)
                        
                except Exception as e:
                    logging.error(f"Error processing date {target_date}: {str(e)}")
                    failed_dates += 1
                    continue
            
            # Summary
            total_time = time.time() - start_time
            logging.info(f"Historical crawler completed!")
            logging.info(f"Successfully processed: {successful_dates} dates")
            logging.info(f"Failed: {failed_dates} dates")
            logging.info(f"Total time: {total_time:.2f} seconds")
            
            if successful_dates > 0:
                return True, f"Successfully processed {successful_dates} dates, {failed_dates} failed"
            else:
                return False, "No dates were successfully processed"
                
        except Exception as e:
            logging.error(f"Historical marketing crawler failed for {self.game_name}: {str(e)}")
            return False, str(e)
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver closed")

def main():
    """Main function to run the historical marketing crawler"""
    print("This script should be run using run_historical_crawler.py")
    print("Please use: python run_historical_crawler.py")

if __name__ == "__main__":
    main()

