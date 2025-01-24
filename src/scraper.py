from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

#TODO fix some categories not finding any results

# Path to folder containing your CSV files
csv_folder = "."

# Name of the output Excel file
output_excel = "combined_excel_file.xlsx"


def extract_group_name(filename):
    """Extract the desired part of the filename (e.g., CL4 from HORIZON-CL4-D3-2024)."""
    parts = filename.split('-')
    if parts[0]=="HORIZON":
        return parts[1]
    else:
        return parts[0]

# Create the 'Probability Rate' column
def calculate_probability_rate(accepted_projects):
    try:
        num_projects = int(accepted_projects)
        if num_projects <= 2:
            return "Low"
        elif num_projects == 3:
            return "Medium"
        elif num_projects >= 4:
            return "High"
    except ValueError:
        return "Unknown"

def format_date(date_string):
    try:
        # Check if there are two dates separated by a space
        dates = date_string.split()
        formatted_dates = []

        for date in dates:
            # Parse each date and format it
            date_object = datetime.strptime(date, "%Y-%m-%d")
            formatted_dates.append(date_object.strftime("%d %b %Y").upper())

        # Join the formatted dates with a space
        return " ".join(formatted_dates)
    except ValueError:
        return date_string  # Return the original string if parsing fails

def combine_spreadsheet(csv_folder_path, output_excel_file):
    """Combine CSV files into grouped Excel sheets based on extracted group name."""
    # Dictionary to store dataframes grouped by the extracted name
    grouped_dataframes = {}

    # Iterate through all CSV files in the folder
    for filename in os.listdir(csv_folder_path):
        if filename.endswith(".csv"):
            # Extract the group name from the filename
            group_name = extract_group_name(filename)

            # Read the CSV file into a DataFrame
            csv_path = os.path.join(csv_folder_path, filename)
            df = pd.read_csv(csv_path)

            # Add the DataFrame to the appropriate group
            if group_name not in grouped_dataframes:
                grouped_dataframes[group_name] = []
            grouped_dataframes[group_name].append(df)

        # Check if there is more than one category
    if len(grouped_dataframes) > 1:
        # Combine all grouped DataFrames and write to an Excel file
        with pd.ExcelWriter(output_excel_file) as writer:
            for group_name, dataframes in grouped_dataframes.items():
                # Concatenate all DataFrames in the group
                combined_df = pd.concat(dataframes, ignore_index=True)
                # Write the combined DataFrame to a sheet
                combined_df.to_excel(writer, sheet_name=group_name, index=False)

        # Apply coloring to the Probability Rate column
        wb = load_workbook(output_excel_file)
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]

            # Find the "Probability Rate" column
            headers = [cell.value for cell in sheet[1]]  # Assuming the first row contains headers
            probability_col_index = headers.index("Probability Rate") + 1

            # Apply coloring
            for row in range(2, sheet.max_row + 1):  # Skip header row
                cell = sheet.cell(row=row, column=probability_col_index)
                if cell.value == "Low":
                    cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6",
                                            fill_type="solid")  # Light blue
                elif cell.value == "Medium":
                    cell.fill = PatternFill(start_color="FFFF00", end_color="FFFF00",
                                            fill_type="solid")  # Yellow
                elif cell.value == "High":
                    cell.fill = PatternFill(start_color="90EE90", end_color="90EE90",
                                            fill_type="solid")  # Green

        # Save the workbook with the applied styles
        wb.save(output_excel_file)

        print(f"All CSV files have been combined and grouped into {output_excel_file}")
    else:
        print("Only one category selected. Skipping Excel file creation.")


def scrape_eu_portal():
    with sync_playwright() as p:
        print("Searching for calls. Please be patient")
        # Launch the browser
        browser = p.chromium.launch(headless=True)  #change to False to run with UI
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

        desired_category = input("\nPlease choose which category you would like to scrape('0' for all): ")

        if desired_category != "0":

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

                    # Extract href link
                    href = title_element['href'] if title_element and title_element.has_attr('href') else "No link"

                    # Append to titles_data
                    titles_data.append({"Identifier": identifier, "Title": title, "Status": status, "Link": href})

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

                            identifier_to_action = {}

                            for row in rows:
                                # Extract identifier and truncate at the first whitespace
                                identifier_element = row.select_one('td:nth-child(1)')
                                raw_identifier = identifier_element.text.strip()
                                identifier = raw_identifier.split(" ")[0] if raw_identifier else "No identifier"

                                # Extract the action type (e.g., RIA, IA)
                                action_match = re.search(r'-(RIA|IA|CSA|MSCA|EIC)', raw_identifier)
                                action_type = action_match.group(1) if action_match else "No action"

                                # Add to the temporary dictionary
                                identifier_to_action[identifier] = action_type

                                # Extract budget
                                raw_budget = row.select_one('td:nth-child(2)').text.strip()
                                budget = raw_budget.replace(" ", "").rstrip(".")

                                # Extract deadline
                                deadline = row.select_one('td:nth-child(5)').text.strip()
                                formatted_deadline = format_date(deadline)

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
                                    "Intensity Rate": "Coming soon",
                                    "Budget": budget,
                                    "Deadline": formatted_deadline,
                                    "Funding Per Project": funding_per_submission,
                                    "Accepted Projects": accepted_submissions
                                })

                            # Merge the Action Type into titles_data using the Identifier as the key
                            for item in titles_data:
                                item["Action"] = identifier_to_action.get(item["Identifier"], "No action")

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
                                        "Identifier": "No identifier found",
                                        "Intensity Rate": "Coming soon",
                                        "Budget": budget,
                                        "Deadline": "No deadline found",
                                        "Funding Per Project": "No funding info",
                                        "Accepted Projects": "No submission info"
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

                # Merge data and save to CSV
            table_df = pd.DataFrame(table_data)
            titles_df = pd.DataFrame(titles_data)
            if not table_df.empty and not titles_df.empty:
                final_df = pd.merge(table_df, titles_df, on="Identifier", how="left")

                final_df['Probability Rate'] = final_df['Accepted Projects'].apply(calculate_probability_rate)

                # Explicitly rearrange columns so 'Action' comes right after 'Identifier'
                columns_order = ['Identifier', 'Action'] + [col for col in final_df.columns if
                                                            col not in ['Identifier', 'Action']]
                final_df = final_df[columns_order]
                final_df.to_csv(f"{selected_option}.csv", index=False)
                print(f"Data saved to {selected_option}.csv")

            # Close the browser
            browser.close()

        else: #fetch all

            for i in range(len(options)):

                if i > 0:
                    # Press the Call button
                    submission_status_button_selector = f"button.eui-button:has-text('{selected_option}')"
                    page.wait_for_selector(submission_status_button_selector, timeout=30000)
                    page.click(submission_status_button_selector)

                    # Define the button selector specifically for the "X" button
                    x_button_selector = 'button.eui-button--basic.eui-button--icon-only[data-e2e="eui-button"] eui-icon-svg[icon="eui-close"]'

                    # Wait for the button to appear and ensure it is visible
                    page.wait_for_selector(x_button_selector, timeout=5000)

                    # Scroll to the button to ensure it's in view
                    page.locator(x_button_selector).scroll_into_view_if_needed()

                    # Click the button
                    try:
                        page.click(x_button_selector)
                        print("X button clicked successfully!")
                        page.wait_for_timeout(2000)

                        submission_status_button_selector = "button.eui-button:has-text('Call')"
                        page.wait_for_selector(submission_status_button_selector, timeout=30000)
                        page.click(submission_status_button_selector)

                        # Scroll INSIDE the menu to find and click the category button
                        for j in range(len(options)):
                            # Get the text of the selected option
                            selected_option = options[i]

                            # Selector for the dropdown container
                            dropdown_container_selector = 'div.eui-u-overflow-auto'
                            # Ensure the dropdown is visible
                            page.locator(dropdown_container_selector).scroll_into_view_if_needed()

                            # Wait for the dropdown container to be available
                            dropdown_container = page.locator(dropdown_container_selector)
                            page.wait_for_selector(dropdown_container_selector, timeout=30000)

                            # Scroll through the dropdown to find the desired option

                            try:
                                # Try to locate the option
                                option = dropdown_container.locator(
                                    f'button.eui-dropdown-item:has(span:text-is("{selected_option}"))')
                                if option.is_visible():
                                    option.scroll_into_view_if_needed()
                                    option.click()
                                    print(f"Clicked on the option: {selected_option}")
                                    break  # Break the while loop to process the next option
                            except Exception:
                                pass

                            # Scroll down inside the dropdown
                            dropdown_container.evaluate('(node) => node.scrollBy(0, 200)')
                            page.wait_for_timeout(500)

                    except Exception as e:
                        print(f"Error clicking the X button: {e}")

                else:
                    selected_option = options[i]
                    # Locate the button with the matching span text
                    matching_button = page.locator(f'button.eui-dropdown-item:has(span:text-is("{selected_option}"))')
                    print(f"Found button for category: {selected_option}")
                    # Click the matching button
                    matching_button.first.click()
                    print("clicked")

                # safety delay
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

                        # Extract href link
                        href = title_element['href'] if title_element and title_element.has_attr('href') else "No link"

                        # Append to titles_data
                        titles_data.append({"Identifier": identifier, "Title": title, "Status": status, "Link": href})

                    # Open the first card to extract table data or fallback to "Total funding available"
                    if len(table_data) == 0:  # Only fetch data from the first card
                        first_call_link_element = call_items[0].select_one(
                            "a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
                        first_call_link = first_call_link_element['href'] if first_call_link_element else None

                        if first_call_link:
                            # Open a new tab for the first call details page
                            new_tab = browser.new_page()
                            new_tab.goto(f"https://ec.europa.eu{first_call_link}")
                            print(f"Opened first call link in a new tab: {first_call_link}")

                            try:
                                # Wait for the table inside the card
                                new_tab.wait_for_selector('table.eui-table', timeout=30000)

                                # Extract table data
                                html = new_tab.content()
                                soup = BeautifulSoup(html, "html.parser")
                                rows = soup.select('table.eui-table tbody tr')

                                identifier_to_action = {}

                                for row in rows:
                                    # Extract identifier and truncate at the first whitespace
                                    identifier_element = row.select_one('td:nth-child(1)')
                                    raw_identifier = identifier_element.text.strip()
                                    identifier = raw_identifier.split(" ")[0] if raw_identifier else "No identifier"

                                    # Extract the action type (e.g., RIA, IA)
                                    action_match = re.search(r'-(RIA|IA|CSA|MSCA|EIC)', raw_identifier)
                                    action_type = action_match.group(1) if action_match else "No action"

                                    # Add to the temporary dictionary
                                    identifier_to_action[identifier] = action_type

                                    # Extract budget
                                    raw_budget = row.select_one('td:nth-child(2)').text.strip()
                                    budget = raw_budget.replace(" ", "").rstrip(".")

                                    # Extract deadline
                                    deadline = row.select_one('td:nth-child(5)').text.strip()
                                    formatted_deadline = format_date(deadline)

                                    # Extract funding per submission
                                    funding_element = row.select_one('td:nth-child(6)')
                                    raw_funding = funding_element.text.strip() if funding_element else "No funding info"
                                    if "to" in raw_funding:
                                        min_funding, max_funding = map(lambda x: x.replace(" ", ""),
                                                                       raw_funding.split("to"))
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
                                        "Intensity Rate": "Coming soon",
                                        "Budget": budget,
                                        "Deadline": formatted_deadline,
                                        "Funding Per Project": funding_per_submission,
                                        "Accepted Projects": accepted_submissions
                                    })

                                # Merge the Action Type into titles_data using the Identifier as the key
                                for item in titles_data:
                                    item["Action"] = identifier_to_action.get(item["Identifier"], "No action")

                            except Exception as e:
                                print("Table not found, attempting fallback to 'Total funding available'")
                                # Attempt to locate the budget in "Total funding available"
                                try:
                                    funding_container = new_tab.locator(
                                        'div.eui-input-group:has(div:has-text("Total funding available"))')
                                    budget_element = funding_container.locator('div.eui-u-font-m')
                                    if budget_element.count() > 0:
                                        raw_budget = budget_element.first.text_content().strip()
                                        budget = raw_budget.replace("\u202f", "").replace(",", "").replace("€",
                                                                                                           "").strip()
                                        table_data.append({
                                            "Identifier": "No identifier found",
                                            "Intensity Rate": "Coming soon",
                                            "Budget": budget,
                                            "Deadline": "No deadline found",
                                            "Funding Per Project": "No funding info",
                                            "Accepted Projects": "No submission info"
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

                    # Merge data and save to CSV
                table_df = pd.DataFrame(table_data)
                titles_df = pd.DataFrame(titles_data)
                if not table_df.empty and not titles_df.empty:
                    final_df = pd.merge(table_df, titles_df, on="Identifier", how="left")
                    # Ensure the 'Action' column exists, even if it's missing in titles_data
                    if 'Action' not in final_df.columns:
                        final_df['Action'] = "No action"

                    final_df['Probability Rate'] = final_df['Accepted Projects'].apply(calculate_probability_rate)

                    # Rearrange columns: 'Identifier', 'Action' first
                    columns_order = ['Identifier', 'Action'] + [col for col in final_df.columns if
                                                                col not in ['Identifier', 'Action']]
                    final_df = final_df[columns_order]
                    final_df.to_csv(f"{selected_option}.csv", index=False)
                    print(f"Data saved to {selected_option}.csv")

                i+=1
        # Close the browser
        browser.close()


scrape_eu_portal()

combine_spreadsheet(csv_folder, output_excel)
