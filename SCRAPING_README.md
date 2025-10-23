# Ministering Interview Scheduler - Import Feature

## Web Scraping Setup

The import feature uses Selenium to scrape companionship data from the LDS Church's LCR ministering page. Since web scraping requires knowledge of the target website's HTML structure, the implementation includes debug tools to help identify the correct CSS selectors.

## First-Time Setup Process

1. **Run the Import** with your LCR credentials
2. **Check for `debug_page.html`** - this file contains the full HTML of the ministering page
3. **Analyze the HTML** using one of these methods:
   - Open `debug_page.html` in a browser and use DevTools (F12) to inspect elements
   - Run `python debug_scraper.py` for automated analysis
4. **Update CSS Selectors** in `app.py` based on what you find
5. **Test Again** with small changes

## Common Selector Patterns to Look For

### Companionship Containers
Look for repeating HTML elements that group member information:
- `<div class="companionship">` or `<section class="group">`
- `<li class="ministering-group">` or `<tr class="companionship-row">`
- Elements with similar structure that repeat for each companionship

### Companionship Names
- `<h3>Companionship Name</h3>`
- `<div class="group-name">Name</div>`
- `<span class="title">Name</span>`

### Member Information
- `<a href="/member/123">Member Name</a>`
- `<div class="member-name">Name</div>`
- `<li class="member">Name</li>`

### Contact Details
- Phone: `<span class="phone">555-123-4567</span>`
- Email: `<a href="mailto:email@example.com">email@example.com</a>`

## Updating the Code

Once you identify the correct selectors, update these variables in the `import_companionships()` function:

```python
# Update these selectors based on the actual HTML
companionship_selectors = ['.actual-companionship-class', '#companionship-container']
comp_name_selectors = ['h3', '.actual-name-class', '.group-title']
member_selectors = ['a.actual-member-link', '.member-name', '.person']
```

## Testing the Selectors

1. Make small changes to the selectors
2. Run the import process
3. Check the Flask console output for debug messages
4. If data is found, proceed to the confirmation page
5. If no data, refine the selectors and try again

## Security Notes

- Only use this with proper authorization from your church leaders
- The scraping process is designed to be respectful and not overload the servers
- Credentials are only used for the scraping session and not stored
- Consider the privacy implications of importing member contact information