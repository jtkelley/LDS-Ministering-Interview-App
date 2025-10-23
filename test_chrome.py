#!/usr/bin/env python3
"""
Test script to isolate Chrome browser setup issues
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def test_chrome_setup():
    print("🔧 Testing Chrome browser setup...")

    try:
        # Configure Chrome options
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in background
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')  # Speed up loading
        options.add_argument('--disable-javascript')  # We'll enable it later if needed
        print(f"🔧 Chrome options configured: {len(options.arguments)} options")

        # Check ChromeDriverManager version and OS detection
        try:
            print(f"🔍 ChromeDriverManager version: {ChromeDriverManager.__version__}")
        except AttributeError:
            print("🔍 ChromeDriverManager version: unknown")
        
        from webdriver_manager.core.os_manager import OperationSystemManager
        os_manager = OperationSystemManager()
        print(f"🔍 Detected OS: {os_manager.get_os_name()}")
        print(f"🔍 Detected architecture: {os_manager.get_os_architecture()}")

        # Test 1: ChromeDriverManager install with explicit architecture
        print("⏳ Testing ChromeDriverManager.install() with explicit win64...")
        start_time = time.time()
        
        # Try to force 64-bit version
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.driver_cache import DriverCacheManager
        
        # Clear any cached drivers first
        cache_manager = DriverCacheManager()
        cache_manager.clear_cache()
        
        # Try installing with specific version approach
        try:
            service_path = ChromeDriverManager().install()
        except Exception as e:
            print(f"Standard install failed: {e}, trying alternative...")
            # Try with specific ChromeType
            from webdriver_manager.core.manager import DriverManager
            manager = DriverManager()
            service_path = manager.install_driver("chrome")
        
        end_time = time.time()
        print(f"✅ ChromeDriverManager.install() completed in {end_time - start_time:.2f} seconds")
        print(f"📁 ChromeDriver path: {service_path}")

        # Check if the file exists and get its properties
        import os
        if os.path.exists(service_path):
            file_size = os.path.getsize(service_path)
            print(f"📊 ChromeDriver file size: {file_size} bytes")
        else:
            print(f"❌ ChromeDriver file does not exist at: {service_path}")

        # Test 2: Create Service object
        print("⏳ Creating Service object...")
        service = Service(service_path)
        print("✅ Service object created")

        # Test 3: Create webdriver.Chrome with minimal options first
        print("⏳ Creating webdriver.Chrome instance with minimal options...")
        minimal_options = webdriver.ChromeOptions()
        minimal_options.add_argument('--headless')
        minimal_options.add_argument('--no-sandbox')
        minimal_options.add_argument('--disable-dev-shm-usage')
        
        start_time = time.time()
        driver = webdriver.Chrome(service=service, options=minimal_options)
        end_time = time.time()
        print(f"✅ webdriver.Chrome created in {end_time - start_time:.2f} seconds")

        # Test 4: Basic navigation
        print("⏳ Testing basic navigation...")
        driver.get('https://www.google.com')
        print("✅ Navigation to Google successful")
        print(f"📄 Page title: {driver.title}")

        # Test 5: Quit driver
        print("⏳ Quitting driver...")
        driver.quit()
        print("✅ Driver quit successfully")

        print("🎉 All Chrome setup tests passed!")

    except Exception as e:
        print(f"❌ Chrome setup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == '__main__':
    success = test_chrome_setup()
    exit(0 if success else 1)