"""
Fixed Homepage Breakdown Extraction - Robust Solution
Dynamically finds the correct featurestatsclass instead of hardcoding it
"""

import re


def extract_homepage_breakdown_from_html_FIXED(page_source):
    """
    FIXED VERSION: Extract homepage breakdown data by dynamically finding the correct class
    
    Works with both English ("Home Page") and Chinese ("主页") page names
    """
    try:
        import re
        
        # Step 1: Find the parent "Home Page" / "主页" row and extract its class number
        # Pattern: Find the row with onclick="ToggleFeatureStats(this, 'featurestatsclass_X')" 
        # that contains <strong>主页</strong> or <strong>Home Page</strong>
        
        parent_pattern = r'onclick="ToggleFeatureStats\(\s*this,\s*\'(featurestatsclass_\d+)\'\s*\);"[^>]*?>[\s\S]{0,500}?<strong>(主页|Home\s+Page)</strong>'
        
        parent_match = re.search(parent_pattern, page_source)
        
        if not parent_match:
            print("ERROR: Could not find Home Page parent row")
            print("Trying alternative patterns...")
            
            # Alternative: Look for the parent row in a different way
            # Find all parent rows first
            all_parents = re.findall(
                r'<div class="tr highlightHover page_stats"[^>]*?onclick="ToggleFeatureStats\(\s*this,\s*\'(featurestatsclass_\d+)\'\s*\);"[^>]*?>([\s\S]{0,800}?)</div>',
                page_source
            )
            
            homepage_class = None
            for class_name, row_content in all_parents:
                if '主页' in row_content or 'Home Page' in row_content:
                    # Verify it's actually in a <strong> tag
                    if re.search(r'<strong>(主页|Home\s+Page)</strong>', row_content):
                        homepage_class = class_name
                        print(f"Found Homepage with class: {homepage_class}")
                        break
            
            if not homepage_class:
                return None
        else:
            homepage_class = parent_match.group(1)
            homepage_name = parent_match.group(2)
            print(f"[OK] Found Homepage parent: '{homepage_name}' uses {homepage_class}")
        
        # Step 2: Find all child rows with this class
        # Pattern: <div class="tr feature_stats {homepage_class}" ...> ... </div> (matching the closing tag of the tr div)
        # We need to capture everything until we find the matching </div> for the opening <div class="tr feature_stats ...">
        
        # Use a more robust pattern that captures content between the opening tr div and its IMMEDIATE closing div
        # But since nested divs exist, we need to be more careful
        
        # Alternative approach: Find all occurrences and extract content more carefully
        child_pattern = rf'<div class="tr feature_stats {homepage_class}"[^>]*?>(.*?)</div>\s*(?=<div class="tr|$)'
        
        child_matches = re.findall(child_pattern, page_source, re.DOTALL)
        
        if not child_matches:
            print(f"ERROR: Found parent class '{homepage_class}' but no child rows with pattern 1")
            # Try alternative: split by the class pattern and process each section
            split_pattern = rf'<div class="tr feature_stats {homepage_class}"[^>]*?>'
            sections = re.split(split_pattern, page_source)
            
            # Skip first section (before first match) and process rest
            child_matches = []
            for section in sections[1:]:
                # Find the content up to the next row or end
                # Look for the end of this row (when we hit another <div class="tr")
                end_match = re.search(r'(.*?)</div>\s*(?=<div class="tr)', section, re.DOTALL)
                if end_match:
                    child_matches.append(end_match.group(1))
                else:
                    # If no next tr found, take content up to the first major closing div
                    end_match2 = re.search(r'(.*?)</div>', section, re.DOTALL)
                    if end_match2:
                        child_matches.append(end_match2.group(1))
            
            if not child_matches:
                print(f"ERROR: Found parent class '{homepage_class}' but no child rows with pattern 2")
                return None
        
        print(f"[OK] Found {len(child_matches)} Homepage child rows")
        
        # Step 3: Process each child row
        homepage_data = []
        
        for row_html in child_matches:
            try:
                # Extract feature name
                name_pattern = r'<strong>([^<]+)</strong>'
                name_match = re.search(name_pattern, row_html)
                if not name_match:
                    continue
                
                page_feature = name_match.group(1).strip()
                
                # Skip empty rows
                if '&nbsp;' in row_html and len(row_html) < 50:
                    continue
                
                # Extract all data values (7 columns)
                td_pattern = r'<div class="td"[^>]*?>([^<]*)</div>'
                all_td_matches = re.findall(td_pattern, row_html)
                
                # Filter: keep only numeric values (skip title, tooltips, etc.)
                data_values = []
                for value in all_td_matches:
                    clean_value = value.strip()
                    if (clean_value and 
                        clean_value != page_feature and
                        clean_value != '&nbsp;' and
                        'expander' not in clean_value and
                        (clean_value.replace(',', '').replace('.', '').replace('%', '').isdigit() or 
                         '.' in clean_value.replace('%', '') or 
                         ',' in clean_value)):
                        data_values.append(clean_value)
                
                # Build row data
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
                
                field_names = ['impressions', 'owner_impressions', 'percentage_of_total_impressions', 
                              'click_thru_rate', 'visits', 'owner_visits', 'percentage_of_total_visits']
                
                for i, value in enumerate(data_values):
                    if i < len(field_names):
                        field_name = field_names[i]
                        
                        if not value.strip():
                            row_data[field_name] = 0
                        else:
                            clean_value = value.strip().replace(',', '')
                            if clean_value.endswith('%'):
                                num_match = re.search(r'([0-9.]+)%?', clean_value)
                                row_data[field_name] = float(num_match.group(1)) if num_match else 0
                            else:
                                try:
                                    row_data[field_name] = int(clean_value)
                                except ValueError:
                                    row_data[field_name] = 0
                
                homepage_data.append(row_data)
                print(f"  [OK] Processed: {page_feature} ({len(data_values)} values)")
                    
            except Exception as e:
                print(f"  [FAIL] Failed to parse row: {str(e)}")
                continue
        
        if homepage_data:
            print(f"[SUCCESS] Successfully extracted {len(homepage_data)} homepage breakdown rows")
            return homepage_data
        else:
            print("[FAIL] No valid homepage breakdown rows found")
            return None
        
    except Exception as e:
        print(f"ERROR in extract_homepage_breakdown: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# Test with the sample HTML files
if __name__ == "__main__":
    import os
    
    print("="*60)
    print("Testing Fixed Homepage Extraction")
    print("="*60)
    
    html_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sample marketing html files')
    
    # Test ALL files
    html_files = sorted([f for f in os.listdir(html_folder) if f.endswith('.html')])
    
    for filename in html_files:
        print(f"\n{'='*60}")
        print(f"Testing: {filename}")
        print('='*60)
        
        filepath = os.path.join(html_folder, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            page_source = f.read()
        
        result = extract_homepage_breakdown_from_html_FIXED(page_source)
        
        if result:
            print(f"\n[SUCCESS]: Extracted {len(result)} rows")
            print("\nFirst 3 items:")
            for item in result[:3]:
                print(f"  - {item['page_feature']}: impressions={item['impressions']}, visits={item['visits']}")
        else:
            print("\n[FAIL] FAILED to extract homepage breakdown")
    
    print(f"\n{'='*60}")
    print("Test Complete")
    print('='*60)

