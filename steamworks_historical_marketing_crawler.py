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

# Import the existing marketing crawler class and translation function
from steamworks_marketing_crawler import SteamworksMarketingCrawler, translate_feature_name_to_english, CHINESE_TO_ENGLISH_FEATURES

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
        """Extract homepage breakdown data from HTML source - SUPPORTS SEASONAL HOMEPAGE"""
        try:
            # Get the page source
            page_source = self.driver.page_source
            import re
            
            homepage_data = []
            
            # Step 1: Search for BOTH homepage variants
            # Find all parent rows - capture until the next <div class="tr feature_stats to get complete row
            all_parents = re.findall(
                r'<div class="tr highlightHover page_stats"[^>]*?onclick="ToggleFeatureStats\(\s*this,\s*\'(featurestatsclass_\d+)\'\s*\);"[^>]*?>(.*?)</div>\s*(?=<div class="tr feature_stats)',
                page_source,
                re.DOTALL
            )
            
            seasonal_homepage = None
            normal_homepage = None
            
            for class_name, row_content in all_parents:
                # Extract the title from <strong> tag
                title_match = re.search(r'<strong>([^<]+)</strong>', row_content)
                if not title_match:
                    continue
                    
                title = title_match.group(1).strip()
                
                # Check if this is seasonal homepage (contains "季节性" AND ("特卖" OR "主页"))
                if '季节性' in title and ('特卖' in title or '主页' in title):
                    # Extract impressions from parent row using the proven td pattern
                    td_pattern = r'<div class="[^"]*\btd\b[^"]*"[^>]*?>(.*?)</div>'
                    all_tds = re.findall(td_pattern, row_content, re.DOTALL)
                    
                    # Clean TD content
                    def strip_html(html_content):
                        text = re.sub(r'<[^>]+>', '', html_content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        return text
                    
                    # Impressions is in TD cell 1 (cell 0 is title)
                    impressions = 0
                    if len(all_tds) > 1:
                        impressions_text = strip_html(all_tds[1]).replace(',', '')
                        if impressions_text.isdigit():
                            impressions = int(impressions_text)
                    
                    seasonal_homepage = {
                        'class': class_name,
                        'title': title,
                        'impressions': impressions
                    }
                    logging.info(f"Found Seasonal Homepage: '{title}' uses {class_name}, impressions: {impressions:,}")
                
                # Check if this is normal homepage (exact match "主页" or "Home Page", without "季节性")
                elif (title == '主页' or title == 'Home Page') and '季节性' not in title:
                    # Extract impressions from parent row using the proven td pattern
                    td_pattern = r'<div class="[^"]*\btd\b[^"]*"[^>]*?>(.*?)</div>'
                    all_tds = re.findall(td_pattern, row_content, re.DOTALL)
                    
                    # Clean TD content
                    def strip_html(html_content):
                        text = re.sub(r'<[^>]+>', '', html_content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        return text
                    
                    # Impressions is in TD cell 1 (cell 0 is title)
                    impressions = 0
                    if len(all_tds) > 1:
                        impressions_text = strip_html(all_tds[1]).replace(',', '')
                        if impressions_text.isdigit():
                            impressions = int(impressions_text)
                    
                    normal_homepage = {
                        'class': class_name,
                        'title': title,
                        'impressions': impressions
                    }
                    logging.info(f"Found Normal Homepage: '{title}' uses {class_name}, impressions: {impressions:,}")
            
            # Step 2: Compare and select which homepage to use
            selected_homepage = None
            
            if seasonal_homepage and normal_homepage:
                # Both found - compare impressions
                if seasonal_homepage['impressions'] > normal_homepage['impressions']:
                    selected_homepage = seasonal_homepage
                    logging.info(f"Selected SEASONAL homepage (impressions: {seasonal_homepage['impressions']:,} > {normal_homepage['impressions']:,})")
                else:
                    selected_homepage = normal_homepage
                    logging.info(f"Selected NORMAL homepage (impressions: {normal_homepage['impressions']:,} >= {seasonal_homepage['impressions']:,})")
            elif seasonal_homepage:
                selected_homepage = seasonal_homepage
                logging.info(f"Only seasonal homepage found, using it")
            elif normal_homepage:
                selected_homepage = normal_homepage
                logging.info(f"Only normal homepage found, using it")
            else:
                logging.warning("Could not find any Home Page variant (seasonal or normal)")
                return []
            
            homepage_class = selected_homepage['class']
            homepage_title = selected_homepage['title']
            
            # Step 2: Find all child rows with this dynamically discovered class
            # FIXED: Use split approach but capture ALL content until next row (same as marketing crawler)
            split_pattern = rf'<div class="tr feature_stats {homepage_class}"[^>]*?>'
            sections = re.split(split_pattern, page_source)
            
            # Process each section to extract the complete row content
            expanded_matches = []
            for section in sections[1:]:
                # Find all content until the next <div class="tr" (which starts the next row)
                # Use GREEDY match .* to capture everything, not just to first </div>
                end_match = re.search(r'(.*)</div>\s*<div class="tr', section, re.DOTALL)
                if end_match:
                    # Found next row - take everything before it
                    expanded_matches.append(end_match.group(1))
                else:
                    # This is the last row or an empty row - take everything until we find the empty row marker
                    end_match2 = re.search(r'(.*)</div>\s*<div class="tr feature_stats_empty', section, re.DOTALL)
                    if end_match2:
                        expanded_matches.append(end_match2.group(1))
                    else:
                        # Take everything up to the end
                        content = section.strip()
                        if content and '<div class="td"' in content:
                            expanded_matches.append(content)
            
            if not expanded_matches:
                logging.warning(f"Found parent class '{homepage_class}' for '{homepage_title}' but no child rows")
                return []
            
            logging.info(f"Found {len(expanded_matches)} expanded rows for '{homepage_title}' with class {homepage_class}")
            
            # Step 2: Process each expanded row with 1% filter
            for row_html in expanded_matches:
                try:
                    # Extract page/feature name
                    name_pattern = r'<strong>([^<]+)</strong>'
                    name_match = re.search(name_pattern, row_html)
                    if not name_match:
                        continue
                    
                    # Get feature name and translate to English
                    page_feature = name_match.group(1).strip()
                    page_feature = translate_feature_name_to_english(page_feature)
                    
                    # Filter out entries that don't belong in homepage breakdown
                    invalid_entries = ['Image', 'Button', 'Primary Store Link', 'Search Auto-complete', 'Discovery Queue']
                    if page_feature in invalid_entries:
                        continue
                    
                    # Helper function to strip HTML tags and extract text
                    def strip_html_tags(html_content):
                        """Remove HTML tags and extract pure text"""
                        text = re.sub(r'<[^>]+>', '', html_content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        return text
                    
                    # Extract all td values - FIXED: Use proven regex approach from marketing crawler
                    # Pattern matches class="td" AND class="td page_type"
                    # Use word boundary to match "td" as a class name
                    td_pattern = r'<div class="[^"]*\btd\b[^"]*"[^>]*?>(.*?)</div>'
                    all_td_matches = re.findall(td_pattern, row_html, re.DOTALL)
                    
                    # FIXED: Keep ALL 7 data cells in positional order (don't filter out empties!)
                    # HTML structure: [title, impressions, owner_impressions, %, click_thru, visits, owner_visits, %, expander]
                    if len(all_td_matches) < 8:
                        logging.warning(f"Homepage row '{page_feature}' has {len(all_td_matches)} td cells, expected 8+, skipping")
                        continue
                    
                    # Extract and clean all 7 data cells (skip cell 0=title, skip cell 8+=expander/extra)
                    data_values = []
                    for i in range(1, 8):  # Cells 1-7 are the data columns
                        if i < len(all_td_matches):
                            clean_value = strip_html_tags(all_td_matches[i])
                            data_values.append(clean_value)
                        else:
                            data_values.append('')  # Pad with empty if missing
                    
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
                    
                    # Map the 7 data values POSITIONALLY to the correct fields
                    field_names = ['impressions', 'owner_impressions', 'percentage_of_total_impressions', 
                                  'click_thru_rate', 'visits', 'owner_visits', 'percentage_of_total_visits']
                    
                    for i, value in enumerate(data_values):
                        if i < len(field_names):
                            field_name = field_names[i]
                            
                            # Parse the value (empty string becomes 0)
                            if not value or value in ['', '&nbsp;', '-']:
                                row_data[field_name] = 0
                            else:
                                # Remove commas and extract number
                                clean_value = value.replace(',', '')
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
                    
                    # APPLY 1% FILTER: Skip row if both percentages are <= 1%
                    percentage_impressions = row_data.get('percentage_of_total_impressions', 0)
                    percentage_visits = row_data.get('percentage_of_total_visits', 0)
                    
                    # GUARD: Only apply filter if we have valid data (not parsing failures)
                    if len(data_values) >= 7 and percentage_impressions <= 1.0 and percentage_visits <= 1.0:
                        continue  # Skip this row, move to next
                    
                    homepage_data.append(row_data)
                    logging.info(f"Processed Home Page expanded row: {page_feature} with {len(data_values)} values")
                        
                except Exception as e:
                    logging.warning(f"Failed to parse Home Page expanded row: {str(e)}")
                    continue
            
            if homepage_data:
                logging.info(f"Homepage breakdown for '{homepage_title}': extracted {len(homepage_data)} rows (after 1% filter)")
                return homepage_data
            else:
                logging.warning(f"No expanded rows found for '{homepage_title}' after 1% filter - homepage_breakdown will be null")
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
                    
                    # Get feature name and translate to English
                    page_feature = name_match.group(1).strip()
                    page_feature = translate_feature_name_to_english(page_feature)
                    
                    # Helper function to strip HTML tags and extract text
                    def strip_html_tags(html_content):
                        """Remove HTML tags and extract pure text"""
                        text = re.sub(r'<[^>]+>', '', html_content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        return text
                    
                    # Extract all td values - FIXED: Handle nested HTML properly
                    # Use a simpler approach that works correctly
                    def extract_td_content(html_content):
                        """Extract content from all td divs, handling nested HTML properly"""
                        td_contents = []
                        # Find all td divs with the correct pattern
                        td_divs = re.findall(r'<div class="td[^"]*"[^>]*>', html_content)
                        
                        for i, td_div in enumerate(td_divs):
                            # Find the start position of this td div
                            start_pos = html_content.find(td_div)
                            if start_pos == -1:
                                continue
                            
                            # Find the content after the opening tag
                            content_start = start_pos + len(td_div)
                            
                            # Look for the next td div or end of content
                            next_td_pos = html_content.find('<div class="td', content_start)
                            if next_td_pos == -1:
                                # Take until the end
                                content = html_content[content_start:]
                            else:
                                # Take until the next td div
                                content = html_content[content_start:next_td_pos]
                            
                            # Clean up the content
                            content = content.strip()
                            td_contents.append(content)
                        
                        return td_contents
                    
                    all_td_matches = extract_td_content(row_html)
                    
                    # FIXED: Keep ALL 7 data cells in positional order (don't filter out empties!)
                    # HTML structure: [title, impressions, owner_impressions, %, click_thru, visits, owner_visits, %, expander]
                    if len(all_td_matches) < 8:
                        logging.warning(f"All-source row '{page_feature}' has {len(all_td_matches)} td cells, expected 8+, skipping")
                        continue
                    
                    # Extract and clean all 7 data cells (skip cell 0=title, skip cell 8+=expander/extra)
                    data_values = []
                    for i in range(1, 8):  # Cells 1-7 are the data columns
                        if i < len(all_td_matches):
                            clean_value = strip_html_tags(all_td_matches[i])
                            data_values.append(clean_value)
                        else:
                            data_values.append('')  # Pad with empty if missing
                    
                    # Parse all data values POSITIONALLY into a dictionary
                    field_names = ['impressions', 'owner_impressions', 'percentage_of_total_impressions', 
                                  'click_thru_rate', 'visits', 'owner_visits', 'percentage_of_total_visits']
                    
                    parsed_values = {}
                    for i, value in enumerate(data_values):
                        if i < len(field_names):
                            field_name = field_names[i]
                            
                            # Parse the value (empty string becomes 0)
                            if not value or value in ['', '&nbsp;', '-']:
                                parsed_values[field_name] = 0
                            else:
                                clean_value = value.replace(',', '')
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
    
    def extract_owner_percentage_from_html(self):
        """Extract owner percentage from HTML source by parsing JavaScript (supports both English and Chinese)"""
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
                # Expected format: 
                # English: [ 'Non-Owners: 74.2%',  74.2 ], [ 'Owners: 25.8%',  25.8 ]
                # Chinese: [ '来自非所有者：65.58%',  65.58 ], [ '来自所有者：34.42%',  34.42 ]
                
                # Look for the Owners entry in both English and Chinese
                owners_patterns = [
                    r"\[\s*'Owners:\s*([0-9.]+)%',\s*([0-9.]+)\s*\]",  # English
                    r"\[\s*'来自所有者：([0-9.]+)%',\s*([0-9.]+)\s*\]"   # Chinese
                ]
                
                for owners_pattern in owners_patterns:
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

