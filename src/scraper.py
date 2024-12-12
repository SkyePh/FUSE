from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

def scrape_eu_portal():
    data = []
    with sync_playwright() as p:
        # Launch the browser
        browser = p.chromium.launch(headless=True)  # Use headless=True to run without UI
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

# ============================ Pagination and Data Extraction =====================================

        next_button_selector = 'button:has(eui-icon-svg[icon="eui-caret-right"][aria-label="Go to next page"])'
        next_icon_selector = 'eui-icon-svg[icon="eui-caret-right"][aria-label="Go to next page"]'

        while True:

            # Wait for results to load
            page.wait_for_selector("sedia-result-card")

            # Extract the HTML content
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Extract results on the current page
            call_items = soup.select("sedia-result-card")
            counter=1
            for item in call_items:
                # Extract title
                title_element = item.select_one("a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
                title = title_element.text.strip() if title_element else "No title"
                print("got it title")

                # Extract identifier
                identifier_element = item.select_one("sedia-result-card-type span.ng-star-inserted")
                identifier = identifier_element.text.strip() if identifier_element else "No identifier"
                print("got it id")

                # Extract deadline
                deadline_element = item.select_one("sedia-result-card-type strong.ng-star-inserted")
                deadline = deadline_element.text.strip() if deadline_element else "No deadline found"
                print("got it deadline")

                # Extract status
                status_element = item.select_one("eui-card-header-right-content eui-chip span.eui-label")
                status = status_element.text.strip() if status_element else "No status found"
                print("got it status")

                # Append data
                data.append({
                    "Title": title,
                    "Identifier": identifier,
                    "Deadline": deadline,
                    "Status": status
                })
                print("appended")
                counter+=1
                print(counter)

            # Locate the "Next" button
            next_button = page.locator(next_button_selector)

            # Debugging output
            print("Checking Next button state...")
            if next_button.count() > 0:
                # Check if the button is disabled
                is_disabled = next_button.evaluate("(button) => button.disabled")
                print(f"Is Next button disabled: {is_disabled}")

                if is_disabled:
                    print("Next button is disabled. Exiting pagination.")
                    break
            else:
                print("Next button not found. Exiting pagination.")
                break

            # Wait for the eui-icon-svg element to appear
            page.wait_for_selector(next_icon_selector, timeout=20000)

            # Locate the icon
            next_icon = page.locator(next_icon_selector)

            # Debugging output
            print("Next icon count:", next_icon.count())
            print("Next icon visible:", next_icon.is_visible())

            # Click the icon if available
            if next_icon.count() > 0 and next_icon.is_visible():
                next_icon.click()
                print("Clicked the 'Next' icon.")
            else:
                print("Next icon not found or not visible. Exiting pagination.")
                break

        # Close the browser
        browser.close()

    # Save the data to a CSV
    df = pd.DataFrame(data)
    df.to_csv("search_results.csv", index=False)
    print("Data saved to search_results.csv")

scrape_eu_portal()
