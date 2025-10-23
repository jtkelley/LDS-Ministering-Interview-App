#!/usr/bin/env python3

from app_scraper import scrape_ministering_data

def test_callback(msg):
    print(f'PROGRESS: {msg}')

print("Testing scraper with dummy credentials...")
result = scrape_ministering_data('test', 'test', test_callback)
print(f'RESULT: {result}')