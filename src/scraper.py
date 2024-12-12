from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

def scrape_eu_portal_with_tags():
    data = []
    with sync_playwright() as p:
        # Launch the browser
        browser = p.chromium.launch(headless=False)  # Use headless=True to run without UI
        page = browser.new_page()

        # Navigate to the portal
        page.goto("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals")

        # Wait for the input field to appear
        search_input_selector = "input[role='combobox']"
        page.wait_for_selector(search_input_selector)

        # Click the input field to focus
        page.click(search_input_selector)

        # Enter a search term (e.g., "HORIZON")
        page.fill(search_input_selector, "HORIZON-CL4")

        # Simulate pressing Enter if required
        page.press(search_input_selector, "Enter")

        # Wait for results to load
        page.wait_for_selector("sedia-result-card")  # Use the tag name directly

        # Extract the HTML content
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Select results by tag
        call_items = soup.select("sedia-result-card")  # Custom tag, no dot prefix needed
        for item in call_items:
            # Extract title
            title_element = item.select_one("eui-u-text-link")  # Custom tag
            title = title_element.text.strip() if title_element else "No title"

            # Extract identifier
            identifier_element = item.select_one("sedia-result-card-type span.ng-star-inserted")  # Custom tag + class
            identifier = identifier_element.text.strip() if identifier_element else "No identifier"

            # Extract deadline
            deadline_element = item.select_one("sedia-result-card-type strong.ng-star-inserted")  # Custom tag + class
            deadline = deadline_element.text.strip() if deadline_element else "No deadline found"

            # Extract status
            status_element = item.select_one("eui-card-header-right-content eui-chip span.eui-label")  # Nested tags
            status = status_element.text.strip() if status_element else "No status found"

            # Append data
            data.append({
                "Title": title,
                "Identifier": identifier,
                "Deadline": deadline,
                "Status": status
            })

        # Close the browser
        browser.close()

    # Save the data to a CSV
    df = pd.DataFrame(data)
    df.to_csv("search_results.csv", index=False)
    print("Data saved to search_results.csv")

scrape_eu_portal_with_tags()
