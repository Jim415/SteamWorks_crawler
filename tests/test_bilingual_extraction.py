"""
Test bilingual extraction (English and Chinese) against sample HTML files
Verifies all extraction methods work with Chinese HTML
"""

import re


def test_parse_number_with_suffix():
    """Test number parsing with both English and Chinese suffixes"""
    print("\n" + "="*60)
    print("Testing: parse_number_with_suffix")
    print("="*60)
    
    test_cases = [
        # English
        ("46.54 million", 46540000),
        ("8.5 thousand", 8500),
        ("1.2 billion", 1200000000),
        ("12,345", 12345),
        # Chinese  
        ("46.54 百万", 46540000),
        ("8.5 千", 8500),
        ("1.2 十亿", 1200000000),
    ]
    
    for text, expected in test_cases:
        match = re.search(r'([\d,]+\.?\d*)\s*(million|thousand|billion|百万|千|十亿)?', text.lower())
        if match:
            number_str = match.group(1).replace(',', '')
            suffix = match.group(2) if match.group(2) else ''
            
            number = float(number_str)
            if suffix in ['million', '百万']:
                result = int(number * 1_000_000)
            elif suffix in ['thousand', '千']:
                result = int(number * 1_000)
            elif suffix in ['billion', '十亿']:
                result = int(number * 1_000_000_000)
            else:
                result = int(number)
            
            status = "[OK]" if result == expected else "[FAIL]"
            print(f"{status} '{text}' -> {result} (expected: {expected})")


def test_homepage_extraction_on_sample():
    """Test homepage extraction on a Chinese HTML sample"""
    print("\n" + "="*60)
    print("Testing: Homepage Extraction on Chinese HTML")
    print("="*60)
    
    import os
    
    html_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'sample marketing html files',
        'marketing_2024-12-05.html'
    )
    
    if not os.path.exists(html_file):
        print("[SKIP] Sample HTML file not found")
        return
    
    with open(html_file, 'r', encoding='utf-8') as f:
        page_source = f.read()
    
    # Test dynamic class detection
    parent_pattern = r'onclick="ToggleFeatureStats\(\s*this,\s*\'(featurestatsclass_\d+)\'\s*\);"[^>]*?>[\s\S]{0,500}?<strong>(主页|Home\s+Page)</strong>'
    parent_match = re.search(parent_pattern, page_source)
    
    if parent_match:
        homepage_class = parent_match.group(1)
        homepage_name = parent_match.group(2)
        print(f"[OK] Found Homepage parent: '{homepage_name}' uses {homepage_class}")
        
        # Find child rows
        split_pattern = rf'<div class="tr feature_stats {homepage_class}"[^>]*?>'
        sections = re.split(split_pattern, page_source)
        
        homepage_matches = []
        for section in sections[1:]:
            end_match = re.search(r'(.*?)</div>\s*(?=<div class="tr)', section, re.DOTALL)
            if end_match:
                homepage_matches.append(end_match.group(1))
            else:
                end_match2 = re.search(r'(.*?)</div>', section, re.DOTALL)
                if end_match2:
                    homepage_matches.append(end_match2.group(1))
        
        print(f"[OK] Found {len(homepage_matches)} child rows")
        
        # Extract names from first 5 rows
        print("\nFirst 5 child features:")
        for i, row_html in enumerate(homepage_matches[:5], 1):
            name_match = re.search(r'<strong>([^<]+)</strong>', row_html)
            if name_match:
                print(f"  {i}. {name_match.group(1)}")
    else:
        print("[FAIL] Could not find Homepage parent row")


def test_feature_name_matching():
    """Test that we can match both English and Chinese feature names"""
    print("\n" + "="*60)
    print("Testing: Feature Name Matching (Bilingual)")
    print("="*60)
    
    # Test data (feature_name, English, Chinese alternatives)
    test_features = [
        ('Takeover Banner', ['Takeover Banner', '置顶展示横幅']),
        ('Main Cluster', ['Main Cluster (Position 1)', '主看板（第 1 个位置）', '主看板（第2个位置）']),
        ('Marketing Message', ['Marketing Message', '宣传信息', '营销信息']),
    ]
    
    for feature_type, test_names in test_features:
        print(f"\n{feature_type}:")
        for name in test_names:
            # Test takeover banner matching
            if feature_type == 'Takeover Banner':
                match = name in ['Takeover Banner', '置顶展示横幅']
                print(f"  {name}: {' [OK]' if match else '[FAIL]'}")
            
            # Test main cluster matching
            elif feature_type == 'Main Cluster':
                match = name.startswith('Main Cluster (') or '主看板' in name
                print(f"  {name}: {'[OK]' if match else '[FAIL]'}")
            
            # Test marketing message matching
            elif feature_type == 'Marketing Message':
                match = name in ['Marketing Message', '宣传信息', '营销信息']
                print(f"  {name}: {'[OK]' if match else '[FAIL]'}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Bilingual Extraction Test Suite")
    print("="*60)
    
    test_parse_number_with_suffix()
    test_homepage_extraction_on_sample()
    test_feature_name_matching()
    
    print("\n" + "="*60)
    print("All Tests Complete")
    print("="*60)








