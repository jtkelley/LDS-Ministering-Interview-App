#!/usr/bin/env python3
"""
Local scraper for debugging LCR ministering login on Windows.
Runs with visible Chrome browser for interactive debugging.
"""

# LCR Credentials - DO NOT HARDCODE - Use environment variables or pass as parameters
# LCR_USERNAME = os.environ.get('LCR_USERNAME')
# LCR_PASSWORD = os.environ.get('LCR_PASSWORD')

import os
import time
import shutil
import requests
import zipfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
def find_existing_chromedriver():
    """Try to find an existing ChromeDriver installation."""
    common_paths = [
        "chromedriver.exe",
        os.path.join(os.getcwd(), "chromedriver.exe"),
        os.path.join(os.getcwd(), "chromedriver", "chromedriver-win64", "chromedriver-win64", "chromedriver.exe"),
        os.path.join(os.getcwd(), "chromedriver-win64", "chromedriver.exe"),  # New download location
        "C:\\Windows\\chromedriver.exe",
        "C:\\chromedriver.exe"
    ]

    for path in common_paths:
        if os.path.exists(path):
            print(f"📍 Found existing ChromeDriver: {path}")
            return path

    # Check PATH
    import shutil
    chromedriver_in_path = shutil.which("chromedriver")
    if chromedriver_in_path:
        print(f"📍 Found ChromeDriver in PATH: {chromedriver_in_path}")
        return chromedriver_in_path

    return None

def download_chromedriver_manual():
    """Manually download ChromeDriver as fallback."""
    try:
        print("🔄 Trying manual ChromeDriver download...")

        # For Chrome 141, we need ChromeDriver 141
        chrome_version = "141"
        chromedriver_version = "141.0.7390.0"

        print(f"📋 Using ChromeDriver version: {chromedriver_version}")

        # Download ChromeDriver for Windows 64-bit
        chromedriver_url = f"https://storage.googleapis.com/chrome-for-testing-public/{chromedriver_version}/win64/chromedriver-win64.zip"
        print(f"📥 Downloading from: {chromedriver_url}")

        response = requests.get(chromedriver_url)

        if response.status_code == 200:
            # Save and extract
            zip_path = "chromedriver_win64.zip"
            with open(zip_path, 'wb') as f:
                f.write(response.content)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall('.')

            os.remove(zip_path)
            chromedriver_path = os.path.join(os.getcwd(), "chromedriver-win64", "chromedriver.exe")
            print(f"✅ Manual ChromeDriver downloaded: {chromedriver_path}")
            return chromedriver_path
        else:
            print(f"❌ Failed to download ChromeDriver manually (HTTP {response.status_code})")
            return None

    except Exception as e:
        print(f"❌ Manual download failed: {e}")
        return None

def setup_chrome_driver():
    """Set up Chrome driver with visible browser for debugging."""
    chrome_options = Options()

    # Make browser visible for debugging - multiple options to ensure visibility
    chrome_options.add_argument("--headless=false")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")  # Added to ensure window is visible
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-images")  # Speed up loading
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    # Note: JavaScript is enabled for login functionality

    # Add user data directory for session persistence
    user_data_dir = os.path.join(os.getcwd(), "chrome_user_data")
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    try:
        # Skip existing ChromeDriver if it's the old version, force download new one
        print("📥 Downloading correct ChromeDriver for Chrome 141...")
        chromedriver_path = download_chromedriver_manual()

        if chromedriver_path and os.path.exists(chromedriver_path):
            print(f"� Using downloaded ChromeDriver: {chromedriver_path}")
        else:
            # Fallback to webdriver-manager
            print("� Falling back to webdriver-manager...")
            chromedriver_path = ChromeDriverManager().install()

        print(f"📍 ChromeDriver path: {chromedriver_path}")

        service = Service(chromedriver_path)

        # Initialize the driver
        print("🚀 Initializing Chrome driver...")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        print("✅ Chrome driver initialized successfully")
        
        # Give the browser window time to fully appear
        time.sleep(2)
        
        return driver

    except Exception as e:
        print(f"❌ All ChromeDriver methods failed: {e}")
        print("🔧 Troubleshooting steps:")
        print("   1. Make sure Google Chrome is installed")
        print("   2. Try deleting the .wdm folder in your user directory")
        print("   3. Check if you have 32-bit vs 64-bit compatibility issues")
        print("   4. Try downloading ChromeDriver manually from https://chromedriver.chromium.org/")
        raise Exception("Could not initialize Chrome driver with any method")

def take_screenshot(driver, name):
    """Take a screenshot for debugging."""
    try:
        screenshot_path = f"screenshot_{name}.png"
        driver.save_screenshot(screenshot_path)
        print(f"📸 Screenshot saved: {screenshot_path}")
    except Exception as e:
        print(f"❌ Failed to take screenshot: {e}")

def save_page_source(driver, name):
    """Save the current page source for debugging."""
    try:
        source_path = f"page_source_{name}.html"
        with open(source_path, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"📄 Page source saved: {source_path}")
    except Exception as e:
        print(f"❌ Failed to save page source: {e}")

def login_to_lcr(driver, username, password):
    """Perform the LCR login process with detailed debugging."""
    try:
        print("🔐 Starting LCR login process...")

        # Step 1: Navigate to LCR ministering page
        print("📍 Step 1: Navigating to LCR ministering page...")
        driver.get("https://lcr.churchofjesuschrist.org/ministering")
        take_screenshot(driver, "01_navigate")
        save_page_source(driver, "01_navigate")

        print(f"📍 Current URL: {driver.current_url}")
        print(f"📍 Page title: {driver.title}")

        # Wait for page to load
        time.sleep(3)

        # Step 2: Enter username
        print("📍 Step 2: Entering username...")
        try:
            # Wait for the username field to be present and visible
            username_field = WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.ID, "username-input"))
            )
            
            # Clear and type username
            username_field.clear()
            username_field.send_keys(username)
            print("✅ Username entered")
            
            # Wait a moment for any JavaScript to process
            time.sleep(1)
            
            take_screenshot(driver, "02_username_entered")
        except TimeoutException:
            print("❌ Username field not found or not visible")
            take_screenshot(driver, "02_username_error")
            save_page_source(driver, "02_username_error")
            return False

        # Step 3: Click Next button
        print("📍 Step 3: Clicking Next button...")
        try:
            # Wait for the Next button to be clickable (enabled)
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "button-primary"))
            )
            next_button.click()
            print("✅ Next button clicked")
            take_screenshot(driver, "03_next_clicked")
            time.sleep(2)
        except TimeoutException:
            print("❌ Next button not clickable")
            take_screenshot(driver, "03_next_error")
            save_page_source(driver, "03_next_error")
            return False

        # Step 4: Enter password
        print("📍 Step 4: Entering password...")
        try:
            password_field = WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.ID, "password-input"))
            )
            password_field.clear()
            password_field.send_keys(password)
            print("✅ Password entered")
            
            # Wait a moment for any JavaScript to process
            time.sleep(1)
            
            take_screenshot(driver, "04_password_entered")
        except TimeoutException:
            print("❌ Password field not found or not visible")
            take_screenshot(driver, "04_password_error")
            save_page_source(driver, "04_password_error")
            return False

        # Step 5: Click Verify/Login button
        print("📍 Step 5: Clicking Verify button...")
        try:
            # Wait for the Verify button to become enabled (not disabled)
            def verify_button_enabled(driver):
                btn = driver.find_element(By.ID, "button-primary")
                return btn.is_enabled()

            WebDriverWait(driver, 10).until(verify_button_enabled)
            verify_button = driver.find_element(By.ID, "button-primary")
            verify_button.click()
            print("✅ Verify button clicked")
            take_screenshot(driver, "05_verify_clicked")
            time.sleep(3)
        except TimeoutException:
            print("❌ Verify button not clickable or not enabled")
            take_screenshot(driver, "05_verify_error")
            save_page_source(driver, "05_verify_error")
            return False


        # Step 6: Wait for ministering page to load
        print("📍 Step 6: Waiting for ministering page to load...")
        WebDriverWait(driver, 30).until(
            lambda driver: "ministering" in driver.current_url.lower() or "companionship" in driver.page_source.lower()
        )
        print("✅ Ministering page loaded successfully")
        take_screenshot(driver, "06_ministering_loaded")
        save_page_source(driver, "06_ministering_loaded")

        # Step 7: Extract ministering data from table
        print("📍 Step 7: Extracting ministering data from table...")
        import csv
        results = []
        try:
            # Wait for the ministering table to load
            table = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
            )
            print("✅ Ministering table found")
            take_screenshot(driver, "07_table_found")

            # Get all rows from the table
            rows = table.find_elements(By.TAG_NAME, "tr")
            print(f"📊 Found {len(rows)} rows in table")

            companionship_counter = 1
            for row_idx, row in enumerate(rows[1:], 1):  # Skip header row
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 7:  # Need at least 7 columns
                        continue

                    # Extract district from first column (might be in header or separate)
                    district_cell = cells[0]
                    district_name = district_cell.text.strip()

                    # Extract interviewer from second column
                    interviewer_cell = cells[1]
                    interviewer = interviewer_cell.text.strip()

                    # Extract ministering brothers from third column
                    ministering_cell = cells[2]
                    brother_links = ministering_cell.find_elements(By.TAG_NAME, "a")

                    # For each brother in this companionship
                    for link in brother_links:
                        name = link.text.strip()
                        if name:
                            # Try to get contact info from popup
                            phone = ""
                            email = ""
                            try:
                                # Click the link to open popup
                                driver.execute_script("arguments[0].scrollIntoView();", link)
                                time.sleep(0.2)
                                link.click()
                                time.sleep(1)

                                # Look for phone and email in popup
                                try:
                                    phone_elem = driver.find_element(By.XPATH, "//a[contains(@href, 'tel:')]")
                                    phone = phone_elem.get_attribute("href").replace("tel:", "")
                                except:
                                    pass

                                try:
                                    email_elem = driver.find_element(By.XPATH, "//a[contains(@href, 'mailto:')]")
                                    email = email_elem.get_attribute("href").replace("mailto:", "")
                                except:
                                    pass

                                # Close popup
                                try:
                                    close_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Close') or @aria-label='Close']")
                                    close_btn.click()
                                except:
                                    driver.find_element(By.TAG_NAME, "body").send_keys("\ue00c")  # Escape key
                                time.sleep(0.5)

                            except Exception as e:
                                print(f"⚠️  Could not get contact info for {name}: {e}")

                            row_data = {
                                'district': district_name,
                                'interviewer': interviewer,
                                'name': name,
                                'phone': phone,
                                'email': email,
                                'companionship_id': companionship_counter
                            }
                            results.append(row_data)

                    companionship_counter += 1

                except Exception as e:
                    print(f"⚠️  Error processing row {row_idx}: {e}")
                    continue

            print(f"✅ Extracted {len(results)} ministering brothers from table")

            # Save results to CSV
            csv_filename = "ministering_brothers.csv"
            with open(csv_filename, mode="w", newline='', encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["district", "interviewer", "name", "phone", "email", "companionship_id"])
                writer.writeheader()
                for row in results:
                    writer.writerow(row)
            print(f"💾 Results saved to {csv_filename}")
            take_screenshot(driver, "07_data_extracted")
            return True

        except Exception as e:
            print(f"❌ Error extracting ministering data: {e}")
            take_screenshot(driver, "07_table_extract_error")
            save_page_source(driver, "07_table_extract_error")
            return False

    except Exception as e:
        print(f"❌ Login error: {e}")
        take_screenshot(driver, "login_exception")
        save_page_source(driver, "login_exception")
        return False

def main():
    """Main function to run the local scraper."""
    print("🚀 Starting Local LCR Ministering Scraper")
    print("=" * 50)

    tables = driver.find_elements(By.TAG_NAME, "table")
    total_links = 0
    total_popups = 0
    total_phone_found = 0
    for table in tables:
        rows = table.find_elements(By.TAG_NAME, "tr")
        for row in rows:
            links = row.find_elements(By.TAG_NAME, "a")
            for link in links:
                link_text = link.text.strip()
                total_links += 1
                try:
                    driver.execute_script("arguments[0].scrollIntoView();", link)
                    driver.execute_script("arguments[0].click();", link)
                except Exception:
                    try:
                        link.click()
                    except Exception:
                        continue
                time.sleep(1.5)
                popup = None
                try:
                    popup = driver.find_element(By.CLASS_NAME, "sc-cd0364fd-0")
                except Exception:
                    pass
                if popup:
                    total_popups += 1
                    phone = ""
                    email = ""
                    phone_elem = popup.find_elements(By.XPATH, ".//*[contains(text(), 'Phone') or contains(text(), 'Cell')]")
                    if phone_elem:
                        phone = phone_elem[0].text.split(":")[-1].strip()
                    email_elem = popup.find_elements(By.XPATH, ".//*[contains(text(), 'E-mail') or contains(text(), 'Email')]")
                    if email_elem:
                        email = email_elem[0].text.split(":")[-1].strip()
                    if phone:
                        total_phone_found += 1
                    for member in ministering_data:
                        if member["name"] == link_text and (not member["email"] or member["email"] == email):
                            member["phone"] = phone
                            member["email"] = email
                            break
                    # Close popup
                    try:
                        close_btn = popup.find_element(By.XPATH, ".//button[contains(text(), 'Close')]")
                        close_btn.click()
                    except Exception:
                        try:
                            driver.execute_script("document.querySelector('.sc-cd0364fd-0 button').click()")
                        except Exception:
                            pass
                    time.sleep(0.5)
    print(f"[SUMMARY] Total name links: {total_links}")
    print(f"[SUMMARY] Popups opened: {total_popups}")

if __name__ == "__main__":
    print("🚀 Local LCR Ministering Scraper")
    print("This script is for debugging. Use the web app for production scraping.")
    print("Set LCR_USERNAME and LCR_PASSWORD environment variables or pass as arguments.")
    # driver = setup_chrome_driver()
    # try:
    #     success = login_to_lcr(driver, os.environ.get('LCR_USERNAME'), os.environ.get('LCR_PASSWORD'))
    #     if success:
    #         print("🎉 Login successful! Ministering data extraction complete.")
    #     else:
    #         print("❌ Login or extraction failed.")
    # finally:
    #     print("🧹 Browser closed")
    #     driver.quit()