from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

def scrape_eu_portal_with_search():
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
        page.wait_for_selector(".sedia-result-card-calls-for-proposals")  # Replace with the actual result card selector

        # Extract the results
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        call_items = soup.select(".sedia-result-card")  # Replace with the actual result card selector
        for item in call_items:
            title = item.select_one(".eui-u-text-link").text.strip() if item.select_one(".eui-u-text-link") else "No title"
            identifier = item.select_one("span.ng-star-inserted").text.strip() if item.select_one("span.ng-star-inserted") else "No identifier"
            data.append({"Title": title, "Identifier": identifier})

        # Close the browser
        browser.close()

    # Save the data to a CSV
    df = pd.DataFrame(data)
    df.to_csv("search_results.csv", index=False)
    print("Data saved to search_results.csv")

scrape_eu_portal_with_search()
