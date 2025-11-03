# Homepage Breakdown Extraction Fix - Complete Summary

## 🔍 **Root Cause Analysis**

### **The Problem**
The Homepage breakdown extraction was **failing 80% of the time** across different dates.

### **Why It Failed**

**Original Code (HARDCODED):**
```python
homepage_pattern = r'<div class="tr feature_stats featurestatsclass_3".*?</div>\s*</div>'
```

**Actual HTML Structure:**
The SteamWorks page uses **dynamic CSS class numbers** that change based on:
- Number of traffic sources on that day
- Order of sources in the table
- Whether certain sources exist or not

**Class Distribution Across 30 Sample Files:**
```
featurestatsclass_1:  2 files  (Dec 5, Dec 11)
featurestatsclass_2:  1 file
featurestatsclass_3:  6 files  ← Original hardcoded value
featurestatsclass_4:  3 files
featurestatsclass_5:  2 files
featurestatsclass_6:  3 files
featurestatsclass_22: 1 file
featurestatsclass_24: 1 file
featurestatsclass_25: 2 files
featurestatsclass_27: 3 files
featurestatsclass_29: 1 file
featurestatsclass_31: 2 files
featurestatsclass_32: 1 file
featurestatsclass_33: 1 file
featurestatsclass_34: 1 file
```

**Success Rate with Hardcoded Class 3:** Only 6/30 = **20%**

---

## ✅ **The Solution**

### **New Approach: Dynamic Class Detection**

Instead of hardcoding `featurestatsclass_3`, we now:

**Step 1: Find the Homepage Parent Row**
```python
# Find the row with onclick="ToggleFeatureStats(this, 'featurestatsclass_X')"
# that contains <strong>主页</strong> or <strong>Home Page</strong>
parent_pattern = r'onclick="ToggleFeatureStats\(\s*this,\s*\'(featurestatsclass_\d+)\'\s*\);"[^>]*?>[\s\S]{0,500}?<strong>(主页|Home\s+Page)</strong>'

parent_match = re.search(parent_pattern, page_source)
homepage_class = parent_match.group(1)  # e.g., "featurestatsclass_27"
```

**Step 2: Find All Child Rows with That Class**
```python
# Use the dynamically discovered class number
split_pattern = rf'<div class="tr feature_stats {homepage_class}"[^>]*?>'
sections = re.split(split_pattern, page_source)

# Extract content from each section
for section in sections[1:]:
    # Extract content up to next row
    end_match = re.search(r'(.*?)</div>\s*(?=<div class="tr)', section, re.DOTALL)
    if end_match:
        child_rows.append(end_match.group(1))
```

**Step 3: Process Each Child Row**
- Same data extraction logic as before
- Parse 7 columns of data
- Apply 1% filter (historical crawler only)

---

## 📊 **Test Results**

### **Test Setup**
- **Sample Size:** 30 HTML files (Dec 5, 2024 - Jan 3, 2025)
- **Language:** Chinese (主页 instead of Home Page)
- **Test Script:** `tests/fix_homepage_extraction.py`

### **Results**
```
✓ 30/30 files (100%) successfully extracted homepage breakdown
✓ 0 failures
✓ Extracted 15-18 rows per file (varies by actual data)
```

### **Sample Output**
```
marketing_2024-12-05.html: featurestatsclass_1  → 17 rows extracted ✓
marketing_2024-12-06.html: featurestatsclass_3  → 17 rows extracted ✓
marketing_2024-12-12.html: featurestatsclass_4  → 17 rows extracted ✓
marketing_2024-12-13.html: featurestatsclass_6  → 18 rows extracted ✓
marketing_2024-12-22.html: featurestatsclass_22 → 17 rows extracted ✓
marketing_2025-01-01.html: featurestatsclass_25 → 17 rows extracted ✓
```

**Before Fix:** 20% success rate (hardcoded class 3)  
**After Fix:** 100% success rate (dynamic detection)

---

## 🔧 **Files Updated**

### **1. `steamworks_marketing_crawler.py`**
**Method:** `extract_homepage_breakdown_from_html()` (Lines 611-712)

**Changes:**
- ✅ Added dynamic parent row detection
- ✅ Extracts class number from onclick attribute
- ✅ Uses discovered class to find child rows
- ✅ Works with both English and Chinese page names
- ✅ Fallback alternative detection method

### **2. `steamworks_historical_marketing_crawler.py`**
**Method:** `extract_homepage_breakdown_from_html()` (Lines 41-184)

**Changes:**
- ✅ Same dynamic detection logic
- ✅ Maintains existing 1% filter logic
- ✅ Bilingual support (English/Chinese)

### **3. `tests/fix_homepage_extraction.py`** (NEW)
**Purpose:** Test harness to verify the fix

**Features:**
- Standalone test script
- Tests extraction against sample HTML files
- Detailed output for debugging
- Can be run independently

---

## 🎯 **Key Improvements**

### **Robustness**
- ✅ **No hardcoded class numbers** - adapts to any class
- ✅ **Bilingual support** - works with English and Chinese
- ✅ **Fallback detection** - multiple patterns to find homepage
- ✅ **Better error handling** - logs which detection method worked

### **Reliability**
- ✅ **100% success rate** across 30 test samples
- ✅ **Handles class numbers 1-34+** (tested range)
- ✅ **Adaptive to page changes** - if new sources appear, class numbers shift, but still works

### **Maintainability**
- ✅ **Self-documenting** - logs which class was found
- ✅ **Easy to debug** - shows detection process in logs
- ✅ **Test coverage** - test script validates against real HTML

---

## 📈 **Impact**

### **Before Fix**
```
30 daily runs:
  ✓ 6 successful homepage extractions (20%)
  ✗ 24 failed extractions (80%)
  
→ Missing critical homepage breakdown data 4 days out of 5
```

### **After Fix**
```
30 daily runs:
  ✓ 30 successful homepage extractions (100%)
  ✗ 0 failures (0%)
  
→ Reliable homepage breakdown data every single day
```

---

## 🔍 **Technical Details**

### **HTML Structure**

**Parent Row (Clickable):**
```html
<div class="tr highlightHover page_stats" onclick="ToggleFeatureStats(this, 'featurestatsclass_1');">
    <div class="td page_type">
        <strong>主页</strong>  <!-- or "Home Page" in English -->
    </div>
    <!-- ... data columns ... -->
    <div class="td expander">...</div>
</div>
```

**Child Rows (Collapsed by Default):**
```html
<div class="tr feature_stats featurestatsclass_1" style="display:none">
    <div class="td">
        <strong>置顶展示横幅</strong>  <!-- Takeover Banner -->
    </div>
    <!-- ... 7 data columns ... -->
</div>

<div class="tr feature_stats featurestatsclass_1" style="display:none">
    <div class="td">
        <strong>主看板（第 1 个位置）</strong>  <!-- Main Cluster Position 1 -->
    </div>
    <!-- ... 7 data columns ... -->
</div>
```

**Key Insight:** The class number in onclick (`featurestatsclass_1`) must match the class in child rows.

---

## 🛠️ **How to Test**

### **Run Test Script**
```powershell
cd D:\Steamworks_Crawler\SteamWorks_crawler
python tests\fix_homepage_extraction.py
```

**Expected Output:**
```
Testing: marketing_2024-12-05.html
[OK] Found Homepage parent: '主页' uses featurestatsclass_1
[OK] Found 17 Homepage child rows
[SUCCESS] Successfully extracted 17 homepage breakdown rows
```

### **Verify in Production**
```powershell
# Run the marketing crawler
python steamworks_marketing_crawler.py

# Check logs
Get-Content steamworks_marketing_crawler.log | Select-String -Pattern "Homepage|featurestatsclass"
```

**Should See:**
```
Found Homepage parent: 'Home Page' uses featurestatsclass_X
Found 15-18 Home Page expanded rows with class featurestatsclass_X
Homepage breakdown: extracted 15-18 rows (after 1% filter)
```

---

## 📝 **Translation Map (Chinese ↔ English)**

| English | Chinese | Notes |
|---------|---------|-------|
| Home Page | 主页 | Parent row |
| Takeover Banner | 置顶展示横幅 | Child feature |
| Main Cluster | 主看板 | Child feature (may have multiple positions) |
| Marketing Message | 宣传信息/营销信息 | Pop-up message |
| What's Trending | 人气蹿升的新品 | Trending section |
| Top Sellers | 热销商品列表 | Best sellers |

The fix handles **both languages automatically** by searching for either pattern.

---

## ⚠️ **Important Notes**

1. **The class number changes dynamically** - never hardcode it
2. **Both languages must be supported** - page language depends on user settings
3. **The split-based regex approach** is more reliable than trying to match nested divs
4. **Empty rows exist** - filter them out during processing
5. **Row count varies** - 15-18 is normal, depends on active features

---

## 🚀 **Next Steps**

1. ✅ **Fix Applied** - Both marketing crawlers updated
2. ✅ **Tested** - 100% success on 30 samples
3. ⏳ **Deploy** - Run production crawler to verify
4. ⏳ **Monitor** - Check logs for successful extraction

---

**Date Fixed:** October 9, 2025  
**Test Coverage:** 30 historical HTML samples (Dec 5, 2024 - Jan 3, 2025)  
**Success Rate:** 30/30 (100%)  
**Files Modified:** 
- `steamworks_marketing_crawler.py`
- `steamworks_historical_marketing_crawler.py`
- `tests/fix_homepage_extraction.py` (new test script)








