from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import re

#TODO implement default option for "all"

def scrape_eu_portal():
    with sync_playwright() as p:
        # Launch the browser
        browser = p.chromium.launch(headless=False)  #change to False to run with UI
        page = browser.new_page()

        # Navigate to the portal
        page.goto("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals")

    # ======================================= Apply Filters ===========================================

        # Press the Programme button
        button_selector = "button[data-e2e='eui-button']:has-text('Programme')"
        page.wait_for_selector(button_selector)
        page.click(button_selector)

        # Press the HORIZON button
        horizon_button_selector = "button.eui-dropdown-item:has-text('Horizon Europe (HORIZON)')"
        page.wait_for_selector(horizon_button_selector, timeout=30000)
        page.click(horizon_button_selector)

        # Press the Call button
        submission_status_button_selector = "button.eui-button:has-text('Call')"
        page.wait_for_selector(submission_status_button_selector, timeout=30000)
        page.click(submission_status_button_selector)

        #============ fetch all the available calls and ask to choose one ====================

        # Selector for the dropdown container
        dropdown_container_selector = 'div.eui-u-overflow-auto'

        # Wait for the dropdown container to load
        page.wait_for_selector(dropdown_container_selector, timeout=30000)

        # Locate the dropdown container
        dropdown_container = page.locator(dropdown_container_selector)

        # Scroll through the dropdown container to ensure all items are visible
        dropdown_container.evaluate('(node) => node.scrollTop = 0')  # Start at the top

        # Continuously scroll until all items are loaded
        previous_item_count = 0
        while True:
            # Get the current number of buttons
            current_item_count = dropdown_container.locator('button.eui-dropdown-item').count()

            if current_item_count > previous_item_count:
                previous_item_count = current_item_count
                # Scroll further down
                dropdown_container.evaluate('(node) => node.scrollBy(0, 200)')
                page.wait_for_timeout(500)  # Wait for the content to load
            else:
                # Stop scrolling if no new items are being loaded
                break

        print(f"Total buttons found after scrolling: {previous_item_count}")

        # Now fetch all the options
        options = []

        # Locate all dropdown buttons
        buttons = dropdown_container.locator('button.eui-dropdown-item')

        for i in range(previous_item_count):
            try:
                # Locate the specific span with 'eui-u-pr-s' class
                span = buttons.nth(i).locator('span.eui-u-pr-s')

                if span.count() > 0:
                    # Extract the text content
                    span_text = span.evaluate('(node) => node.childNodes[0]?.nodeValue').strip()
                    options.append(span_text)
                else:
                    print(f"No relevant span found for button {i}.")
            except Exception as e:
                print(f"Error processing button {i}: {e}")

        # Print all extracted options
        print("Extracted Options:", options)

        #==================================== get input =========================================

        menu_option_call = 1
        for i in range(len(options)):
            print(menu_option_call, ") ", options[i])
            menu_option_call += 1

        desired_category = input("\nPlease choose which category you would like to scrape: ")

        try:
            # Convert user input to index
            desired_index = int(desired_category) - 1

            if 0 <= desired_index < len(options):
                # Get the text of the selected option
                selected_option = options[desired_index]

                # Locate the button with the matching span text
                matching_button = page.locator(f'button.eui-dropdown-item:has(span:text-is("{selected_option}"))')

                if matching_button.count() > 0:
                    print(f"Found button for category: {selected_option}")
                    # Click the matching button
                    matching_button.first.click()
                    print("clicked")
                else:
                    print(f"No button found for the selected category: {selected_option}")
            else:
                print("Invalid selection. Please choose a valid option from the menu.")
        except ValueError:
            print("Invalid input. Please enter a number corresponding to the menu options.")


    # ============================ Pagination and Data Extraction =====================================

        #safety delay
        page.wait_for_timeout(5000)

        next_button_selector = 'button:has(eui-icon-svg[icon="eui-caret-right"][aria-label="Go to next page"])'
        next_icon_selector = 'eui-icon-svg[icon="eui-caret-right"][aria-label="Go to next page"]'

        # Initialize data containers
        titles_data = []
        table_data = []

        while True:
            # Wait for results to load
            page.wait_for_selector("sedia-result-card")

            # Extract the HTML content
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Extract results on the current page
            call_items = soup.select("sedia-result-card")

            for item in call_items:
                # Extract title (name)
                title_element = item.select_one("a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
                title = title_element.text.strip() if title_element else "No title"

                # Extract identifier
                identifier_element = item.select_one("sedia-result-card-type span.ng-star-inserted")
                identifier = identifier_element.text.strip() if identifier_element else "No identifier"

                # Extract status
                status_element = item.select_one("eui-card-header-right-content eui-chip span.eui-label")
                status = status_element.text.strip() if status_element else "No status found"

                # Append to titles_data
                titles_data.append({"Identifier": identifier, "Title": title, "Status": status})

            # Open the first card to extract table data or fallback to "Total funding available"
            if len(table_data) == 0:  # Only fetch data from the first card
                first_call_link_element = call_items[0].select_one("a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
                first_call_link = first_call_link_element['href'] if first_call_link_element else None

                if first_call_link:
                    # Open a new tab for the first call details page
                    new_tab = browser.new_page()
                    new_tab.goto(f"https://ec.europa.eu{first_call_link}")
                    print(f"Opened first call link in a new tab: {first_call_link}")

                    try:
                        # Wait for the table inside the card
                        new_tab.wait_for_selector('table.eui-table', timeout=10000)

                        # Extract table data
                        html = new_tab.content()
                        soup = BeautifulSoup(html, "html.parser")
                        rows = soup.select('table.eui-table tbody tr')

                        for row in rows:
                            # Extract identifier and truncate at the first whitespace
                            identifier_element = row.select_one('td:nth-child(1)')
                            raw_identifier = identifier_element.text.strip()
                            identifier = raw_identifier.split(" ")[0] if raw_identifier else "No identifier"

                            # Extract budget
                            raw_budget = row.select_one('td:nth-child(2)').text.strip()
                            budget = raw_budget.replace(" ", "").rstrip(".")

                            # Extract deadline
                            deadline = row.select_one('td:nth-child(5)').text.strip()

                            # Extract funding per submission
                            funding_element = row.select_one('td:nth-child(6)')
                            raw_funding = funding_element.text.strip() if funding_element else "No funding info"
                            if "to" in raw_funding:
                                min_funding, max_funding = map(lambda x: x.replace(" ", ""), raw_funding.split("to"))
                                funding_per_submission = f"Min: {min_funding} Max: {max_funding}"
                            elif "around" in raw_funding:
                                funding_per_submission = f"~ {raw_funding.replace('around', '').strip()}"
                            else:
                                funding_per_submission = raw_funding

                            # Extract accepted submissions
                            accepted_submissions = row.select_one('td:nth-child(7)').text.strip()

                            # Append to table_data
                            table_data.append({
                                "Identifier": identifier,
                                "Budget": budget,
                                "Deadline": deadline,
                                "Funding Per Submission": funding_per_submission,
                                "Accepted Submissions": accepted_submissions
                            })

                    except Exception as e:
                        print("Table not found, attempting fallback to 'Total funding available'")
                        # Attempt to locate the budget in "Total funding available"
                        try:
                            funding_container = new_tab.locator(
                                'div.eui-input-group:has(div:has-text("Total funding available"))')
                            budget_element = funding_container.locator('div.eui-u-font-m')
                            if budget_element.count() > 0:
                                raw_budget = budget_element.first.text_content().strip()
                                budget = raw_budget.replace("\u202f", "").replace(",", "").replace("€", "").strip()
                                table_data.append({
                                    "Identifier": "Fallback Identifier",
                                    "Budget": budget,
                                    "Deadline": "No deadline found",
                                    "Funding Per Submission": "No funding info",
                                    "Accepted Submissions": "No submission info"
                                })
                                print(f"Extracted Budget from fallback: {budget}")
                            else:
                                print("No budget found in fallback.")
                        except Exception as fallback_error:
                            print(f"Error during fallback extraction: {fallback_error}")

                    finally:
                        # Close the new tab after extraction
                        new_tab.close()

            page.wait_for_selector(next_button_selector)
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
                print("waiting for 30 sec to load next page")
                page.wait_for_timeout(30000)
            else:
                print("Next icon not found or not visible. Exiting pagination.")
                break


        # Close the browser
        browser.close()

    # Merge titles_data with table_data
    table_df = pd.DataFrame(table_data)
    titles_df = pd.DataFrame(titles_data)
    final_df = pd.merge(table_df, titles_df, on="Identifier", how="left")
    columns_order = ["Title"] + [col for col in final_df.columns if col != "Title"]
    final_df = final_df[columns_order]
    # Save to CSV
    final_df.to_csv("call_data.csv", index=False)
    print("Data saved to call_data.csv")

scrape_eu_portal()
