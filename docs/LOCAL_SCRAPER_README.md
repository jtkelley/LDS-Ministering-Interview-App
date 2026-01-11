# Local LCR Ministering Scraper

This script allows you to debug the LCR login process locally on Windows with a visible Chrome browser.

## Setup

1. **Edit Credentials**: Open `local_scraper.py` and replace the placeholder values at the top:
   ```python
   LCR_USERNAME = "your_actual_lcr_username"
   LCR_PASSWORD = "your_actual_lcr_password"
   ```

2. **ChromeDriver Setup** (Optional): If you have ChromeDriver issues, you can manually place `chromedriver.exe` in the `chromedriver/chromedriver-win64/chromedriver-win64/` folder. The script will automatically find and use it.

3. **Run the scraper**:
   ```
   run_local_scraper.bat
   ```

## What it does

- Opens a visible Chrome browser window
- Navigates to the LCR ministering page
- Attempts to login using the multi-step process (username → Next → password → Verify)
- Takes screenshots at each step for debugging
- Saves page source HTML files for analysis
- Waits for you to press Enter before closing

## Debugging Files

The script will create several files in the current directory:
- `screenshot_01_navigate.png` - Initial page load
- `screenshot_02_username_entered.png` - After entering username
- `screenshot_03_next_clicked.png` - After clicking Next
- `screenshot_04_password_entered.png` - After entering password
- `screenshot_05_verify_clicked.png` - After clicking Verify
- `screenshot_06_ministering_loaded.png` - Final ministering page (if successful)
- `page_source_*.html` - HTML source at each step

## Troubleshooting

- If login fails, check the screenshots to see what the page looks like at each step
- Use the saved HTML files with the `debug_scraper.py` script to analyze the page structure
- The browser window will stay open until you press Enter, so you can inspect it manually
- **ChromeDriver issues**: Place `chromedriver.exe` in `chromedriver/chromedriver-win64/chromedriver-win64/` folder

## Notes

- JavaScript is enabled for proper login functionality
- Chrome user data is stored in `chrome_user_data/` and cleaned up between runs
- The script will automatically download the correct ChromeDriver version