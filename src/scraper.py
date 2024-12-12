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

        # # Wait for the input field to appear
        # search_input_selector = "input[role='combobox']"
        # page.wait_for_selector(search_input_selector)
        #
        # # Click the input field to focus
        # page.click(search_input_selector)
        #
        # # Enter a search term (e.g., "HORIZON")
        # page.fill(search_input_selector, "HORIZON")
        #
        # # Simulate pressing Enter if required
        # page.press(search_input_selector, "Enter")

# ============================ Apply Filters =====================================

        # Wait for the filter button to appear
        button_selector = "button[data-e2e='eui-button']:has-text('All filters')"  # Using the unique data-e2e attribute
        page.wait_for_selector(button_selector)

        # Click the button
        page.click(button_selector)

        # Wait for the HORIZON button to appear
        button_selector = "button[role='menuitem']:has-text('Horizon Europe (HORIZON)')"
        page.wait_for_selector(button_selector)

        # Click the button
        page.click(button_selector)

        # Wait for the toggle button to appear
        toggle_button_selector = "button[data-e2e='eui-button'][aria-label='Toggle Global Challenges and European Industrial Competitiveness']"
        page.wait_for_selector(toggle_button_selector)

        # Click the toggle button
        page.click(toggle_button_selector)

        # Wait for the checkbox within the specific <li> element
        checkbox_selector = "li[title='Digital, Industry and Space'] input.eui-input-checkbox"
        page.wait_for_selector(checkbox_selector)
        # Click the checkbox
        page.click(checkbox_selector)

        # Wait for the checkbox
        checkbox_selector = "input.eui-input-checkbox[name='31094503']"
        page.wait_for_selector(checkbox_selector)
        # Click the checkbox
        page.click(checkbox_selector)

        # Wait for the button to appear
        button_selector = "button[aria-label='Primary']:has-text('View results')"
        page.wait_for_selector(button_selector)
        # Click the button
        page.click(button_selector)

#=======================================================================================================

        # Wait for results to load
        page.wait_for_selector("sedia-result-card")  # Use the tag name directly

        # Extract the HTML content
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Select results by tag
        call_items = soup.select("sedia-result-card")  # Custom tag, no dot prefix needed
        for item in call_items:
            # Extract title
            title_element = item.select_one("a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
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
