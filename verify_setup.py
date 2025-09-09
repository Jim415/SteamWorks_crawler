#!/usr/bin/env python3
"""
SteamWorks Crawler - Setup Verification Script
This script verifies that all components are properly configured for production use.
"""

import sys
import os
import mysql.connector
from mysql.connector import Error

def check_python_version():
    """Check if Python version is compatible"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires Python 3.8+")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    print("\n🔍 Checking dependencies...")
    required_packages = ['selenium', 'mysql-connector-python']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'mysql-connector-python':
                import mysql.connector
                print(f"✅ {package} - Installed")
            else:
                __import__(package.replace('-', '_'))
                print(f"✅ {package} - Installed")
        except ImportError:
            print(f"❌ {package} - Missing")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    return True

def check_database_connection():
    """Check database connection"""
    print("\n🔍 Checking database connection...")
    
    # Import database config from test_database.py
    try:
        # Execute test_database.py to get the config
        import subprocess
        result = subprocess.run([sys.executable, 'test_database.py'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✅ Database connection test passed")
            return True
        else:
            print("❌ Database connection test failed")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Cannot test database connection: {e}")
        return False
    
    return True  # Already tested above

def check_files():
    """Check if required files exist"""
    print("\n🔍 Checking required files...")
    required_files = [
        'steamworks_crawler.py',
        'requirements.txt',
        'setup_database.sql',
        'test_database.py',
        'check_database.py'
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} - Found")
        else:
            print(f"❌ {file} - Missing")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n⚠️  Missing files: {', '.join(missing_files)}")
        return False
    return True

def check_virtual_environment():
    """Check if virtual environment is active"""
    print("\n🔍 Checking virtual environment...")
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment is active")
        return True
    else:
        print("⚠️  Virtual environment not detected")
        print("Recommended: source venv/bin/activate (Linux/Mac) or venv\\Scripts\\activate (Windows)")
        return True  # Not critical, just a warning

def main():
    """Main verification function"""
    print("=== SteamWorks Crawler - Setup Verification ===\n")
    
    checks = [
        check_python_version(),
        check_dependencies(),
        check_database_connection(),
        check_files(),
        check_virtual_environment()
    ]
    
    print("\n" + "="*50)
    print("VERIFICATION SUMMARY")
    print("="*50)
    
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"🎉 All {total} checks passed! Setup is ready for production.")
        print("\nNext steps:")
        print("1. Run: python steamworks_crawler.py")
        print("2. Or use: ./run_crawler.sh (Linux/Mac) or run_crawler.bat (Windows)")
        print("3. Check logs: steamworks_crawler.log")
        return 0
    else:
        print(f"⚠️  {passed}/{total} checks passed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Install dependencies: pip install -r requirements.txt")
        print("- Setup database: mysql -u root -p < setup_database.sql")
        print("- Update database config in test_database.py")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 