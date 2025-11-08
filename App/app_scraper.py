#!/usr/bin/env python3
"""
Integrated scraper for the Flask app - extracts ministering data from LCR JSON.
This is a modified version of local_scraper.py for headless operation in the web app.
"""

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
import json
import csv

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
    """Set up Chrome driver with platform detection (Windows/Linux)."""
    print("🔍 [DEBUG] setup_chrome_driver called")

    # Detect platform
    import platform
    is_windows = platform.system() == 'Windows'
    is_linux = platform.system() == 'Linux'

    print(f"🖥️  Detected platform: {platform.system()}")

    chrome_options = Options()

    # Headless mode for production/Docker, visible for local debugging on Windows
    if is_linux or os.environ.get('FLASK_ENV') == 'production':
        print("🐧 Running in headless mode (Linux/Production)")
        chrome_options.add_argument("--headless")
    else:
        print("🪟 Running in visible mode (Windows/Development)")
        chrome_options.add_argument("--headless=false")
        chrome_options.add_argument("--start-maximized")

    # Common options for all platforms
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
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
        chromedriver_path = None

        # On Linux (Docker), use webdriver-manager to auto-download ChromeDriver
        if is_linux:
            print("🐧 Linux detected - using webdriver-manager for ChromeDriver")
            chromedriver_path = ChromeDriverManager().install()
            print(f"✅ ChromeDriver installed via webdriver-manager: {chromedriver_path}")

        # On Windows, try to use local ChromeDriver first
        elif is_windows:
            print("🪟 Windows detected - checking for local ChromeDriver")
            chromedriver_path = download_chromedriver_manual()

            if not chromedriver_path or not os.path.exists(chromedriver_path):
                print("🔄 Local ChromeDriver not found, falling back to webdriver-manager...")
                chromedriver_path = ChromeDriverManager().install()

        # Fallback for other platforms
        else:
            print("🔄 Using webdriver-manager...")
            chromedriver_path = ChromeDriverManager().install()

        print(f"📍 ChromeDriver path: {chromedriver_path}")

        service = Service(chromedriver_path)

        print("🔍 [DEBUG] About to initialize Chrome driver")
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

def login_to_lcr(driver, username, password, progress_callback=None):
    """Perform the LCR login process and extract ministering data from JSON.
    Returns the extracted data as a list of dictionaries."""
    print("🔍 [DEBUG] login_to_lcr called")
    try:
        print("🔍 [DEBUG] Starting login process")
        if progress_callback:
            progress_callback("🔐 Starting LCR login process...")

        # Step 1: Navigate to LCR ministering page
        print("🔍 [DEBUG] Step 1: Navigating to LCR")
        if progress_callback:
            progress_callback("📍 Step 1: Navigating to LCR ministering page...")
        try:
            driver.get("https://lcr.churchofjesuschrist.org/ministering")
            print("🔍 [DEBUG] Navigation completed")
            if progress_callback:
                progress_callback(f"📍 Current URL: {driver.current_url}")
                progress_callback(f"📍 Page title: {driver.title}")
        except Exception as e:
            print(f"🔍 [DEBUG] Navigation failed: {e}")
            if progress_callback:
                progress_callback(f"❌ Navigation failed: {e}")
            return None

        # Wait for page to load and check if we're on the right page
        print("🔍 [DEBUG] Waiting for page to load")
        if progress_callback:
            progress_callback("📍 Waiting for login page to load...")
        time.sleep(3)

        # Check if we got redirected or if there's an error
        current_url = driver.current_url
        page_title = driver.title
        print(f"🔍 [DEBUG] After navigation - URL: {current_url}, Title: {page_title}")
        if progress_callback:
            progress_callback(f"📍 After navigation - URL: {current_url}")
            progress_callback(f"📍 Page title: {page_title}")

        # Check for common error conditions - be more specific to avoid false positives
        if ("error" in page_title.lower() and "sign in" not in page_title.lower()) or ("error" in driver.page_source.lower() and "oauth" not in driver.page_source.lower()):
            print("🔍 [DEBUG] Error page detected")
            if progress_callback:
                progress_callback("❌ Error page detected - possible login issue or site problem")
            return None

        if "maintenance" in page_title.lower() or "maintenance" in driver.page_source.lower():
            print("🔍 [DEBUG] Maintenance page detected")
            if progress_callback:
                progress_callback("❌ Site under maintenance")
            return None

        # Step 2: Enter username - handle both direct and OAuth login
        print("🔍 [DEBUG] Step 2: Looking for username field")
        if progress_callback:
            progress_callback("📍 Step 2: Entering username...")
        try:
            # Try OAuth login first (id="username"), then fallback to direct (id="username-input")
            username_selectors = [(By.ID, "username"), (By.ID, "username-input")]
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located(selector)
                    )
                    print(f"🔍 [DEBUG] Username field found with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not username_field:
                raise TimeoutException("No username field found")
            
            username_field.clear()
            username_field.send_keys(username)
            print("🔍 [DEBUG] Username entered")
            if progress_callback:
                progress_callback("✅ Username entered")
            time.sleep(1)
        except TimeoutException:
            print("🔍 [DEBUG] Username field not found")
            if progress_callback:
                progress_callback("❌ Username field not found or not visible")
                progress_callback(f"📄 Current page source contains username field: {'username' in driver.page_source or 'username-input' in driver.page_source}")
            return None

        # Step 3: Click Next button
        if progress_callback:
            progress_callback("📍 Step 3: Clicking Next button...")
        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "button-primary"))
            )
            next_button.click()
            if progress_callback:
                progress_callback("✅ Next button clicked")
            time.sleep(2)
        except TimeoutException:
            if progress_callback:
                progress_callback("❌ Next button not clickable")
            return None

        # Step 4: Enter password - handle both direct and OAuth login
        if progress_callback:
            progress_callback("📍 Step 4: Entering password...")
        try:
            # Try OAuth login first (id="password"), then fallback to direct (id="password-input")
            password_selectors = [(By.ID, "password"), (By.ID, "password-input")]
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located(selector)
                    )
                    print(f"🔍 [DEBUG] Password field found with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not password_field:
                raise TimeoutException("No password field found")
            
            password_field.clear()
            password_field.send_keys(password)
            if progress_callback:
                progress_callback("✅ Password entered")
            time.sleep(1)
        except TimeoutException:
            if progress_callback:
                progress_callback("❌ Password field not found or not visible")
            return None

        # Step 5: Click Verify/Login button
        if progress_callback:
            progress_callback("📍 Step 5: Clicking Verify button...")
        try:
            # Try multiple button selectors for OAuth vs direct login
            button_selectors = [(By.ID, "button-primary"), (By.ID, "login-button"), (By.CSS_SELECTOR, "button[type='submit']")]
            verify_button = None
            for selector in button_selectors:
                try:
                    def button_enabled(driver):
                        btn = driver.find_element(*selector)
                        return btn.is_enabled() and btn.is_displayed()
                    
                    WebDriverWait(driver, 5).until(button_enabled)
                    verify_button = driver.find_element(*selector)
                    print(f"🔍 [DEBUG] Verify button found with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not verify_button:
                raise TimeoutException("No verify button found")
            
            verify_button.click()
            if progress_callback:
                progress_callback("✅ Verify button clicked")
            time.sleep(3)
        except TimeoutException:
            if progress_callback:
                progress_callback("❌ Verify button not clickable or not enabled")
            return None

        # Step 6: Wait for ministering page to load
        if progress_callback:
            progress_callback("📍 Step 6: Waiting for ministering page to load...")
        WebDriverWait(driver, 30).until(
            lambda driver: "ministering" in driver.current_url.lower() or "companionship" in driver.page_source.lower()
        )
        if progress_callback:
            progress_callback("✅ Ministering page loaded successfully")

        # Step 7: Try to extract from JSON first, fall back to table scraping if needed
        if progress_callback:
            progress_callback("📍 Step 7: Attempting JSON extraction...")
        results = []
        json_extraction_success = False
        
        try:
            # First check if the script element exists
            try:
                script = driver.find_element(By.ID, "__NEXT_DATA__")
                if progress_callback:
                    progress_callback("✅ Found __NEXT_DATA__ script element")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"❌ Could not find __NEXT_DATA__ script: {e}")
                raise Exception("JSON script not found")

            # Get the script content
            try:
                script_content = script.get_attribute("innerHTML")
                if progress_callback:
                    progress_callback(f"📄 Script content length: {len(script_content)} characters")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"❌ Could not get script content: {e}")
                raise Exception("Could not get script content")

            # Parse the JSON
            try:
                data = json.loads(script_content)
                if progress_callback:
                    progress_callback("✅ JSON parsed successfully")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"❌ JSON parsing failed: {e}")
                raise Exception("JSON parsing failed")

            # Extract ministering data from the parsed JSON
            try:
                ministering = data["props"]["pageProps"]["initialState"]["ministeringData"]
                if progress_callback:
                    progress_callback("✅ Found ministeringData in JSON")
            except KeyError as e:
                if progress_callback:
                    progress_callback(f"❌ ministeringData not found in JSON structure. Available keys: {list(data.keys()) if 'props' in data else 'No props key'}")
                raise Exception("ministeringData not found in JSON")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"❌ Error accessing ministeringData: {e}")
                raise Exception("Error accessing ministeringData")

            companionship_counter = 1
            for district in ministering.get("elders", []):
                district_name = district.get("districtName", "")
                interviewer = district.get("supervisorName", "")
                for companionship in district.get("companionships", []):
                    companionship_id = companionship_counter
                    for minister in companionship.get("ministers", []):
                        name = minister.get("name", "")
                        phone = minister.get("phone", "") if "phone" in minister else ""
                        email = minister.get("email", "") if "email" in minister else ""
                        row = {
                            'district': district_name,
                            'interviewer': interviewer,
                            'name': name,
                            'phone': phone,
                            'email': email,
                            'companionship_id': companionship_id
                        }
                        results.append(row)
                    companionship_counter += 1

            if progress_callback:
                progress_callback(f"✅ Extracted {len(results)} ministering brothers from JSON")
            json_extraction_success = True

        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ JSON extraction failed: {e}")
                progress_callback("🔄 Falling back to table scraping approach...")

        # If JSON extraction failed, use the table scraping approach that was working
        if not json_extraction_success:
            if progress_callback:
                progress_callback("📍 Extracting ministering data from table...")
            try:
                # Wait for the ministering table to load
                table = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                )
                if progress_callback:
                    progress_callback("✅ Ministering table found")

                # Get all rows from the table
                rows = table.find_elements(By.TAG_NAME, "tr")
                if progress_callback:
                    progress_callback(f"📊 Found {len(rows)} rows in table")

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
                                    if progress_callback:
                                        progress_callback(f"⚠️ Could not get contact info for {name}: {e}")

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
                        if progress_callback:
                            progress_callback(f"⚠️ Error processing row {row_idx}: {e}")
                        continue

                if progress_callback:
                    progress_callback(f"✅ Extracted {len(results)} ministering brothers from table")

            except Exception as e:
                if progress_callback:
                    progress_callback(f"❌ Error extracting ministering data from table: {e}")
                return None

        # Augment with phone/email from popups for members missing data (only if we got data from JSON)
        if json_extraction_success:
            if progress_callback:
                progress_callback("📍 Step 8: Augmenting with popup data from ministering brothers column...")
            try:
                # Find the ministering table
                table = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                )
                
                total_links = 0
                total_popups = 0
                total_phone_found = 0
                total_email_found = 0

                # Get all rows from the table
                rows = table.find_elements(By.TAG_NAME, "tr")
                print(f"🔍 [DEBUG] Found {len(rows)} rows for popup extraction")
                
                for row_idx, row in enumerate(rows[1:], 1):  # Skip header row
                    cells = row.find_elements(By.TAG_NAME, "td")
                    print(f"🔍 [DEBUG] Row {row_idx}: has {len(cells)} cells")
                    if len(cells) < 3:  # Need at least 3 columns (district, interviewer, ministering brothers)
                        print(f"🔍 [DEBUG] Row {row_idx}: skipped - not enough cells")
                        continue
                    
                    # Debug: print what's in each cell
                    for cell_idx, cell in enumerate(cells[:5]):  # Print first 5 cells
                        print(f"🔍 [DEBUG] Row {row_idx}, Cell {cell_idx}: '{cell.text[:50] if cell.text else '(empty)'}'")
                    
                    # Check column 1 (index 1, second column) for ministering brother links
                    ministering_cell = cells[1]
                    brother_links = ministering_cell.find_elements(By.TAG_NAME, "a")
                    print(f"🔍 [DEBUG] Row {row_idx}, Cell 1: found {len(brother_links)} links")
                    
                    for link in brother_links:
                        link_text = link.text.strip()
                        if not link_text:
                            continue
                        total_links += 1
                        print(f"🔍 [DEBUG] Processing link {total_links}: {link_text}")

                        # Try to open popup for this ministering brother
                        try:
                            driver.execute_script("arguments[0].scrollIntoView();", link)
                            time.sleep(0.2)
                            try:
                                link.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", link)
                            time.sleep(1)

                            # Look for popup - try different selectors
                            popup = None
                            try:
                                popup = driver.find_element(By.CLASS_NAME, "sc-cd0364fd-0")
                                print(f"🔍 [DEBUG] Popup found with class 'sc-cd0364fd-0' for {link_text}")
                            except Exception:
                                try:
                                    popup = driver.find_element(By.CSS_SELECTOR, "[role='dialog']")
                                    print(f"🔍 [DEBUG] Popup found with role='dialog' for {link_text}")
                                except Exception:
                                    print(f"🔍 [DEBUG] No popup found for {link_text}")

                            if popup:
                                total_popups += 1
                                phone = ""
                                email = ""

                                # Extract phone from tel: link
                                try:
                                    phone_elem = popup.find_element(By.XPATH, ".//a[contains(@href, 'tel:')]")
                                    phone = phone_elem.get_attribute("href").replace("tel:", "").strip()
                                    print(f"🔍 [DEBUG] Phone found for {link_text}: {phone}")
                                    if phone:
                                        total_phone_found += 1
                                except Exception:
                                    print(f"🔍 [DEBUG] No phone link found for {link_text}")

                                # Extract email from mailto: link
                                try:
                                    email_elem = popup.find_element(By.XPATH, ".//a[contains(@href, 'mailto:')]")
                                    email = email_elem.get_attribute("href").replace("mailto:", "").strip()
                                    print(f"🔍 [DEBUG] Email found for {link_text}: {email}")
                                    if email:
                                        total_email_found += 1
                                except Exception:
                                    print(f"🔍 [DEBUG] No email link found for {link_text}")

                                # Update matching row in results
                                for row_data in results:
                                    if row_data['name'] == link_text:
                                        if phone and not row_data['phone']:
                                            row_data['phone'] = phone
                                            print(f"🔍 [DEBUG] Updated phone for {link_text}")
                                        if email and not row_data['email']:
                                            row_data['email'] = email
                                            print(f"🔍 [DEBUG] Updated email for {link_text}")
                                        break

                                # Close popup
                                try:
                                    close_btn = popup.find_element(By.XPATH, ".//button[contains(text(), 'Close') or @aria-label='Close']")
                                    close_btn.click()
                                    print(f"🔍 [DEBUG] Closed popup for {link_text}")
                                except Exception:
                                    try:
                                        driver.find_element(By.TAG_NAME, "body").send_keys("\ue00c")  # Escape key
                                        print(f"🔍 [DEBUG] Closed popup with Escape for {link_text}")
                                    except Exception:
                                        print(f"🔍 [DEBUG] Could not close popup for {link_text}")
                                time.sleep(0.5)

                        except Exception as e:
                            print(f"🔍 [DEBUG] Error processing popup for {link_text}: {e}")

                print(f"🔍 [DEBUG] Popup extraction summary:")
                print(f"  - Total links processed: {total_links}")
                print(f"  - Popups opened: {total_popups}")
                print(f"  - Phone numbers found: {total_phone_found}")
                print(f"  - Emails found: {total_email_found}")
                
                if progress_callback:
                    progress_callback(f"[SUMMARY] Processed {total_links} ministering brother links")
                    progress_callback(f"[SUMMARY] Opened {total_popups} popups")
                    progress_callback(f"[SUMMARY] Found {total_phone_found} phone numbers")
                    progress_callback(f"[SUMMARY] Found {total_email_found} emails")
                    
            except Exception as e:
                print(f"🔍 [DEBUG] Error during popup augmentation: {e}")
                if progress_callback:
                    progress_callback(f"[WARN] Could not augment with popups: {e}")

        if progress_callback:
            progress_callback(f"✅ Scraping complete! Extracted {len(results)} ministering brothers")
        return results

    except Exception as e:
        if progress_callback:
            progress_callback(f"❌ Login process failed: {e}")
        return None

def scrape_ministering_data(username, password, progress_callback=None):
    """Main function to scrape ministering data for the web app.
    Returns a list of ministering brother dictionaries or None on failure."""
    print("🔍 [DEBUG] scrape_ministering_data called with username length:", len(username) if username else 0)
    driver = None
    try:
        print("🔍 [DEBUG] About to call setup_chrome_driver()")
        if progress_callback:
            progress_callback("🚀 Initializing Chrome driver for scraping...")

        driver = setup_chrome_driver()
        print("🔍 [DEBUG] setup_chrome_driver() completed successfully")

        if progress_callback:
            progress_callback("🔐 Starting login and data extraction...")

        print("🔍 [DEBUG] About to call login_to_lcr()")
        results = login_to_lcr(driver, username, password, progress_callback)
        print("🔍 [DEBUG] login_to_lcr() completed, results:", "None" if results is None else f"list with {len(results)} items")

        if results is not None:
            if progress_callback:
                progress_callback(f"✅ Successfully extracted {len(results)} ministering brothers")
            print("🔍 [DEBUG] Returning successful results")
            return results
        else:
            if progress_callback:
                progress_callback("❌ Failed to extract ministering data")
            print("🔍 [DEBUG] login_to_lcr returned None")
            return None

    except Exception as e:
        print(f"🔍 [DEBUG] Exception caught in scrape_ministering_data: {e}")
        import traceback
        print("🔍 [DEBUG] Full traceback:")
        traceback.print_exc()
        if progress_callback:
            progress_callback(f"❌ Scraping failed: {e}")
        return None
    finally:
        print("🔍 [DEBUG] In finally block, about to close driver")
        if driver:
            try:
                driver.quit()
                print("🔍 [DEBUG] Driver closed successfully")
                if progress_callback:
                    progress_callback("🧹 Chrome driver closed")
            except Exception as e:
                print(f"🔍 [DEBUG] Error closing driver: {e}")
                if progress_callback:
                    progress_callback(f"⚠️ Warning: Could not close driver properly: {e}")

if __name__ == "__main__":
    # For testing the scraper standalone
    import sys
    if len(sys.argv) != 3:
        print("Usage: python app_scraper.py <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    def print_progress(message):
        print(message)

    results = scrape_ministering_data(username, password, print_progress)

    if results:
        print(f"\n✅ Scraping successful! Extracted {len(results)} ministering brothers.")
        print("Sample data:")
        for i, row in enumerate(results[:3]):
            print(f"  {i+1}. {row['name']} - {row['district']} - {row['phone']} - {row['email']}")
        if len(results) > 3:
            print(f"  ... and {len(results)-3} more")
    else:
        print("❌ Scraping failed!")
        sys.exit(1)