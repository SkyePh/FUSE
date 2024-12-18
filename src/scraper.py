from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import re

#TODO fix budgets
#TODO fetch call specifiers and keep then in array

def scrape_eu_portal():
    data = []
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

        page.wait_for_timeout(5000)
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

            for item in call_items:

                # Extract title
                title_element = item.select_one("a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
                title = title_element.text.strip() if title_element else "No title"

                # Extract identifier
                identifier_element = item.select_one("sedia-result-card-type span.ng-star-inserted")
                identifier = identifier_element.text.strip() if identifier_element else "No identifier"

                # Extract status
                status_element = item.select_one("eui-card-header-right-content eui-chip span.eui-label")
                status = status_element.text.strip() if status_element else "No status found"

                print("Fetched Item")

                #here we open the card and read budget and then go back mayube??

                # Extract link to call details
                link_element = item.select_one("a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
                call_link = link_element['href'] if link_element else "No link"

                # Initialize budget details
                budget = "No budget found"
                funding_per_submission = "No funding info"
                accepted_submissions = "No submission info"

                # Navigate to the call details page
                if call_link != "No link":
                    # Open the call link in a new tab
                    call_tab = browser.new_page()
                    call_tab.goto(f"https://ec.europa.eu{call_link}")
                    print(f"Opened link: {call_link}")

                    try:
                        # Wait for the div containing the deadline
                        deadline_container = call_tab.locator('div.col-sm-4:has-text("Deadline date")')

                        # Fetch the second child div directly
                        deadline_element = deadline_container.locator('div:nth-child(2)')
                        if deadline_element:
                            deadline_text = deadline_element.text_content().strip()

                            # Use regex to extract the date
                            match = re.search(r'\d{1,2} [A-Za-z]+ \d{4}', deadline_text)
                            deadline = match.group(0) if match else "No deadline found"
                        else:
                            deadline = "No deadline found"

                        print(f"Extracted Deadline: {deadline}")

                    except Exception as e:
                        print(f"Error fetching deadline: {e}")
                        deadline = "No deadline found"

                    try:
                        budget_section = call_tab.locator('eui-card:has-text("Budget overview")')

                        # Wait for the table inside the Budget Overview card
                        call_tab.wait_for_selector('table.eui-table', timeout=30000)
                        table = budget_section.locator('table.eui-table')

                        # Extract and clean the budget
                        budget_element = table.locator('td').nth(1)
                        if budget_element:
                            raw_budget = budget_element.text_content().strip()
                            # Remove spaces and any trailing dot
                            budget = raw_budget.replace(" ", "").rstrip(".")
                        else:
                            budget = "No budget found"

                        # Extract and process funding per submission
                        funding_element = table.locator('div.eui-u-text-wrap').nth(1)
                        if funding_element:
                            raw_funding = funding_element.text_content().strip()
                            if "to" in raw_funding:
                                min_funding, max_funding = map(lambda x: x.replace(" ", ""), raw_funding.split("to"))
                                funding_per_submission = f"Min: {min_funding} Max: {max_funding}"
                            elif "around" in raw_funding:
                                funding_per_submission = f"~ {raw_funding.replace('around', '').strip()}"
                            else:
                                funding_per_submission = raw_funding  # In case of an unexpected format
                        else:
                            funding_per_submission = "No funding info"

                        # Extract number of accepted submissions
                        accepted_element = table.locator('div.eui-u-text-wrap').nth(2)
                        accepted_submissions = (
                            accepted_element.text_content().strip() if accepted_element else "No submission info"
                        )

                        print(
                            f"Budget: {budget}, Funding per submission: {funding_per_submission}, Accepted submissions: {accepted_submissions}"
                        )

                    except Exception as e:
                        print(f"Error fetching budget information: {e}")
                        budget = "No budget found"
                        funding_per_submission = "No funding info"
                        accepted_submissions = "No submission info"

                    # Close the call tab and return to the main tab
                    call_tab.close()

                # Append data
                data.append({
                    "Title": title,
                    "Identifier": identifier,
                    "Deadline": deadline,
                    "Status": status,
                    "Budget": budget,
                    "Funding Per Submission": funding_per_submission,
                    "Accepted Submissions": accepted_submissions
                })

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

    # Save the data to a CSV
    df = pd.DataFrame(data)
    df.to_csv("search_results.csv", index=False)
    print("Data saved to search_results.csv")

scrape_eu_portal()
