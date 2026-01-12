#!/usr/bin/env python3
"""
Local scraper for debugging LCR ministering login on Windows.
Runs with visible Chrome browser and saves screenshots/page source for debugging.

This is a thin wrapper around app_scraper.py - all scraping logic is maintained
in one place.
"""

import os
import sys
import csv
import getpass

# Add parent directory to path so we can import app_scraper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_scraper import setup_chrome_driver, login_to_lcr


def print_progress(message, **kwargs):
    """Wrapper for print that ignores extra kwargs from progress_callback."""
    print(message)


def save_to_csv(results, filename="ministering_brothers.csv"):
    """Save results to CSV file."""
    if not results:
        print("No results to save.")
        return None

    with open(filename, mode="w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["district", "interviewer", "name", "phone", "email", "companionship_id"])
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"Saved {len(results)} records to {filename}")
    return filename


def main():
    print("=" * 60)
    print("Local LCR Ministering Scraper")
    print("=" * 60)
    print()

    # Prompt for credentials
    username = input("LCR Username: ")
    password = getpass.getpass("LCR Password: ")

    if not username or not password:
        print("Username and password are required.")
        return

    # Ask about group (Brothers or Sisters)
    print()
    print("Which group to scrape?")
    print("  1. Brothers (Elders Quorum)")
    print("  2. Sisters (Relief Society)")
    group_choice = input("Enter 1 or 2 [1]: ").strip()
    group = "sisters" if group_choice == "2" else "brothers"

    # Ask about browser visibility
    print()
    show_browser = input("Show browser window? (y/n) [y]: ").strip().lower()
    show_browser = show_browser != 'n'  # Default to yes

    print()
    print(f"Starting scraper for {group}...")
    if show_browser:
        print("(Browser window should appear)")
    print()

    driver = None
    try:
        # Setup driver
        driver, _ = setup_chrome_driver(headless=not show_browser, debug_mode=False)

        # Run the scraper
        results = login_to_lcr(
            driver,
            username,
            password,
            progress_callback=print_progress,
            debug_mode=False,
            group=group
        )

        if results:
            print()
            print(f"Successfully extracted {len(results)} records!")
            save_to_csv(results, filename=f"ministering_{group}.csv")
        else:
            print()
            print("Scraping failed.")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        if driver:
            if show_browser:
                input("\nPress Enter to close the browser...")
            driver.quit()
            print("Browser closed.")


if __name__ == "__main__":
    main()
