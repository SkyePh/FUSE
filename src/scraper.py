from playwright.async_api import async_playwright
import asyncio
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
import json
from database import store_call, store_category, get_category_id

# Save results in JSON format
results_json_path = "scraped_results.json"

# Path to folder containing your CSV files
csv_folder = "."

# Name of the output Excel file
output_excel = "combined_excel_file.xlsx"

async def status_click(page, status_dict, selected_statuses, all_filters_selector):
    """
    Opens the 'All Filters' menu, checks/unchecks statuses, and applies additional filters.

    Args:
        page: The Playwright page instance.
        status_dict: A dictionary mapping status names to their HTML checkbox IDs.
        selected_statuses: A dictionary specifying which statuses should be checked (True) or unchecked (False).
        all_filters_selector: The CSS selector for the 'All Filters' button.
    """

    # Step 1: Open the "All Filters" menu (stays open)
    await page.click(all_filters_selector)
    await asyncio.sleep(2)  # Allow time for filters to fully expand

    # Step 2: Apply status filters
    for status, checkbox_id in status_dict.items():
        checkbox = page.locator(f"input.eui-input-checkbox[id='{checkbox_id}']")
        is_checked = await checkbox.is_checked()

        should_be_checked = selected_statuses.get(status, False)

        if should_be_checked and not is_checked:
            await checkbox.click()
            print(f"Checked {status}.")
        elif not should_be_checked and is_checked:
            await checkbox.click()
            print(f"Unchecked {status}.")

    # Step 3 (Optional): Apply date filters if needed
    # Example: Setting a "From Date" field
    # from_date_selector = "input[placeholder='From Date']"  # Adjust this selector based on actual HTML
    # await page.fill(from_date_selector, "2024-01-01")  # Example date

    # Step 4: Click "Apply Filters" if necessary (Modify selector accordingly)
    apply_button_selector = "button:has-text('View results')"  # Adjust this based on actual button
    await page.click(apply_button_selector)
    await asyncio.sleep(2)  # Wait for filters to be applied

    print("Filters applied successfully.")



def extract_group_name(filename):
    """Extract the desired part of the filename"""
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

def format_openingdate(date_string):
    try:
        # Convert ISO date string (YYYY-MM-DD) to a date object
        date_obj = datetime.strptime(date_string, "%Y-%m-%d").date()
        return date_obj
    except ValueError:
        return None

def format_date(date_string):
    try:
        tokens = date_string.split()
        # Process tokens in groups of three (for each date)
        date_objects = []
        for i in range(0, len(tokens), 3):
            chunk = " ".join(tokens[i:i+3])
            # Parse using the format in the scraped string ("17 April 2023")
            date_obj = datetime.strptime(chunk, "%d %B %Y").date()
            date_objects.append(date_obj)
        # If only one date is present, return the date object; otherwise, return a tuple
        return date_objects[0] if len(date_objects) == 1 else tuple(date_objects)
    except ValueError:
        # If parsing fails, you might want to return None or handle the error as needed
        return None


async def scrape_eu_portal(closed_option, forthcoming_option, open_option, keyword = None, desired_category: list = None, get_categories_only: bool = False):
    async with async_playwright() as p:

        # Create "scraping in progress" flag
        open("scraping_in_progress.json", "w").close()

        print("Searching for calls. Please be patient")
        # Launch the browser
        browser = await p.chromium.launch(headless=True)  #change to False to run with UI
        page = await browser.new_page()

        # Navigate to the portal
        await page.goto("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals")

    # ======================================= Apply Filters ===========================================

        # Press the Programme button
        button_selector = "button[data-e2e='eui-button']:has-text('Programme')"
        await page.wait_for_selector(button_selector)
        await page.click(button_selector)

        # Press the HORIZON button
        horizon_button_selector = "button.eui-dropdown-item:has-text('Horizon Europe (HORIZON)')"
        await page.wait_for_selector(horizon_button_selector, timeout=30000)
        await page.click(horizon_button_selector)

        status_dict = {
            "closed": "31094503",  # Checkbox ID for Closed
            "forthcoming": "31094501",  # Checkbox ID for Forthcoming
            "open": "31094502"  # Checkbox ID for Open
        }

        selected_statuses = {
            "closed": closed_option,  # User wants "Closed" selected
            "forthcoming": forthcoming_option,  # User wants "Forthcoming" unselected
            "open": open_option  # User wants "Open" selected
        }

        filters_menu_selector = "button.eui-button:has-text('All filters')"  # The selector for the all filters

        await status_click(page, status_dict, selected_statuses, filters_menu_selector)



        # Press the Call button
        submission_status_button_selector = "button.eui-button:has-text('Call')"
        await page.wait_for_selector(submission_status_button_selector, timeout=30000)
        await page.click(submission_status_button_selector)

        #============ fetch all the available calls and ask to choose one ====================

        # Selector for the dropdown container
        dropdown_container_selector = 'div.eui-u-overflow-auto'

        # Wait for the dropdown container to load
        await page.wait_for_selector(dropdown_container_selector, timeout=30000)

        # Locate the dropdown container
        dropdown_container = page.locator(dropdown_container_selector)

        # Scroll through the dropdown container to ensure all items are visible
        await dropdown_container.evaluate('(node) => node.scrollTop = 0')  # Start at the top

        # Continuously scroll until all items are loaded
        previous_item_count = 0
        max_scroll_attempts = 10  # Prevent infinite scrolling

        for _ in range(max_scroll_attempts):
            current_item_count = await dropdown_container.locator('button.eui-dropdown-item').count()

            if current_item_count > previous_item_count:
                previous_item_count = current_item_count
                await dropdown_container.evaluate('(node) => node.scrollBy(0, 200)')
                await asyncio.sleep(0.5)  # Use asyncio.sleep()
            else:
                break  # Exit loop if no new items are loaded

        print(f"Total buttons found after scrolling: {previous_item_count}")

        # Now fetch all the options
        options = []

        # Locate all dropdown buttons
        buttons = dropdown_container.locator('button.eui-dropdown-item')

        for i in range(previous_item_count):
            try:
                # Locate the specific span with 'eui-u-pr-s' class
                span = buttons.nth(i).locator('span.eui-u-pr-s')

                # Extract the text content
                span_text = await span.evaluate('(node) => node.childNodes[0]?.nodeValue')
                if span_text:
                    span_text = span_text.strip()
                options.append(span_text)

            except Exception as e:
                print(f"Error processing button {i}: {e}")

        # Print all extracted options
        print("Extracted Options:", options)

        for category in options:
            await store_category(category)

        #==================================== get input =========================================

        menu_option_call = 1
        for i in range(len(options)):
            print(menu_option_call, ") ", options[i])
            menu_option_call += 1

        if get_categories_only:
            await browser.close()
            return options  # Return list of categories to `/home`

        selected_categories = [category for category in desired_category if category in options]

        if "0" in desired_category:  # If "0" is provided, select all
            selected_categories = options

        print(selected_categories)

        # ============================ Pagination and Data Extraction =====================================

        counter_for_menu = 0
        for category in selected_categories:
            await asyncio.sleep(0.5)  # 500ms
            if counter_for_menu > 0:
                # Press the Call button
                submission_status_button_selector = f"button.eui-button:has-text('{selected_categories[counter_for_menu - 1]}')"
                await page.wait_for_selector(submission_status_button_selector, timeout=30000)
                await page.click(submission_status_button_selector)

                # Define the button selector specifically for the "X" button
                x_button_selector = 'button.eui-button--basic.eui-button--icon-only[data-e2e="eui-button"] eui-icon-svg[icon="eui-close"]'

                # Wait for the button to appear and ensure it is visible
                await page.wait_for_selector(x_button_selector, timeout=5000)

                # Scroll to the button to ensure it's in view
                await page.locator(x_button_selector).scroll_into_view_if_needed()

                # Click the button
                try:
                    await page.click(x_button_selector)
                    print("X button clicked successfully!")
                    await asyncio.sleep(2)

                    submission_status_button_selector = "button.eui-button:has-text('Call')"
                    await page.wait_for_selector(submission_status_button_selector, timeout=30000)
                    await page.click(submission_status_button_selector)

                    # Scroll INSIDE the menu to find and click the category button
                    for j in range(len(selected_categories)):

                        # Selector for the dropdown container
                        dropdown_container_selector = 'div.eui-u-overflow-auto'
                        # Ensure the dropdown is visible
                        await page.locator(dropdown_container_selector).scroll_into_view_if_needed()

                        # Wait for the dropdown container to be available
                        dropdown_container = page.locator(dropdown_container_selector)
                        await page.wait_for_selector(dropdown_container_selector, timeout=30000)

                        # Scroll through the dropdown to find the desired option

                        try:
                            # Try to locate the option
                            option = dropdown_container.locator(
                                f'button.eui-dropdown-item:has(span:text-is("{category}"))')
                            if await option.is_visible():
                                await option.scroll_into_view_if_needed()
                                await option.click()
                                print(f"Clicked on the option: {category}")
                                break  # Break the while loop to process the next option
                        except Exception:
                            pass

                        # Scroll down inside the dropdown
                        await dropdown_container.evaluate('(node) => node.scrollBy(0, 200)')
                        await asyncio.sleep(0.5)  # 500ms

                except Exception as e:
                    print(f"Error clicking the X button: {e}")

            else:
                # Locate the button with the matching span text
                matching_button = page.locator(f'button.eui-dropdown-item:has(span:text-is("{category}"))')
                print(f"Found button for category: {category}")
                # Click the matching button
                await matching_button.first.click()
                print("clicked")

            # safety delay
            await asyncio.sleep(5)  # 5s

            next_button_selector = 'button:has(eui-icon-svg[icon="eui-caret-right"][aria-label="Go to next page"])'
            next_icon_selector = 'eui-icon-svg[icon="eui-caret-right"][aria-label="Go to next page"]'

            # Initialize data containers
            titles_data = []
            table_data = []

            while True:
                # Wait for results to load
                await page.wait_for_selector("sedia-result-card")

                # Extract the HTML content
                html = await page.content()
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
                    titles_data.append({"Identifier": identifier, "Title": title, "Status": status, "Link": "https://ec.europa.eu"+href})

                # Open the first card to extract table data or fallback to "Total funding available"
                if len(table_data) == 0:  # Only fetch data from the first card
                    first_call_link_element = call_items[0].select_one(
                        "a.eui-u-text-link.eui-u-font-l.eui-u-font-regular")
                    first_call_link = first_call_link_element['href'] if first_call_link_element else None

                    if first_call_link:
                        # Open a new tab for the first call details page
                        new_tab = await browser.new_page()
                        await new_tab.goto(f"https://ec.europa.eu{first_call_link}")
                        print(f"Opened first call link in a new tab: {first_call_link}")

                        try:
                            # Wait for the table inside the card
                            await new_tab.wait_for_selector('table.eui-table', timeout=30000)

                            # Extract table data
                            html = await new_tab.content()
                            soup = BeautifulSoup(html, "html.parser")
                            rows = soup.select('table.eui-table tbody tr')

                            identifier_to_action = {}

                            header_cells = soup.select('table.eui-table thead tr th')

                            headers = [cell.get_text(strip=True) for cell in header_cells]
                            deadline_index = headers.index("Deadline") + 1
                            open_date_index = headers.index("Opening date") + 1
                            funding_per_sub_index = headers.index("Contributions") + 1
                            budget_index_first = 2
                            budget_index_last = headers.index("Stages")



                            accepted_projects_index = None
                            for idx, h in enumerate(headers, start=1):
                                normalized = h.replace("\n", " ").strip().lower()
                                if "indicative number" in normalized and "grants" in normalized:
                                    accepted_projects_index = idx
                                    break
                            if accepted_projects_index is None:
                                raise ValueError("Accepted Projects column not found")


                            for row in rows:
                                # Extract identifier and truncate at the first whitespace
                                identifier_element = row.select_one('td:nth-child(1)')
                                raw_identifier = identifier_element.text.strip()
                                identifier = raw_identifier.split(" ")[0] if raw_identifier else "No identifier"

                                # Extract the action type (e.g., RIA, IA)
                                action_match = re.search(r'-(RIA|IA|CSA|MSCA|EIC)', raw_identifier)
                                action_type = action_match.group(1) if action_match else "No action"

                                open_date_element = row.select_one(f'td:nth-child({open_date_index})').text.strip()
                                formatted_opendate = format_openingdate(open_date_element)
                                print('bruh3')

                                # Add to the temporary dictionary
                                identifier_to_action[identifier] = action_type

                                # Extract budget
                                raw_budget = row.select_one(f'td:nth-child({budget_index_first})').text.strip()
                                budget = raw_budget.replace(" ", "").rstrip(".")

                                # Iterate over the remaining budget columns until we hit "Stages".
                                for i in range(budget_index_first + 1, budget_index_last):
                                    cell = row.select_one(f'td:nth-child({i})')
                                    if cell:
                                        value = cell.text.strip()
                                        if value != "":  # update only if non-empty
                                            budget = value.replace(" ", "").rstrip(".")

                                print('bruh4')
                                # Extract deadline
                                deadline = row.select_one(f'td:nth-child({deadline_index})').text.strip()
                                formatted_deadline = format_date(deadline)

                                print('bruh5')
                                # Extract funding per submission
                                funding_element = row.select_one(f'td:nth-child({funding_per_sub_index})')
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
                                accepted_submissions = row.select_one(f'td:nth-child({accepted_projects_index})').text.strip()

                                print('bruh6')
                                # Append to table_data
                                table_data.append({
                                    "Identifier": identifier,
                                    "Intensity Rate": "Coming soon",
                                    "Opening Date": formatted_opendate,
                                    "Budget": budget,
                                    "Deadline": formatted_deadline,
                                    "Funding Per Project": funding_per_submission,
                                    "Accepted Projects": accepted_submissions
                                })

                            print('bruh7')
                            # Merge the Action Type into titles_data using the Identifier as the key
                            for item in titles_data:
                                item["Action"] = identifier_to_action.get(item["Identifier"], "No action")
                            print('bruh8')
                        except Exception as e:
                            print("Table not found, attempting fallback to 'Total funding available'")
                            # Attempt to locate the budget in "Total funding available"
                            try:
                                funding_container =  new_tab.locator(
                                    'div.eui-input-group:has(div:has-text("Total funding available"))')
                                budget_element = funding_container.locator('div.eui-u-font-m')
                                if await budget_element.count() > 0:
                                    raw_budget = (await budget_element.first.text_content()).strip()
                                    budget = raw_budget.replace("\u202f", "").replace(",", "").replace("€",
                                                                                                       "").strip()
                                    table_data.append({
                                        "Identifier": "No identifier found",
                                        "Intensity Rate": "Coming soon",
                                        "Budget": budget,
                                        "Deadline": "No deadline found",
                                        "Opening Date": "No opening date found",
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
                            await new_tab.close()

                await page.wait_for_selector(next_button_selector)
                # Locate the "Next" button
                next_button = page.locator(next_button_selector)
                # Debugging output
                print("Checking Next button state...")
                if  await next_button.count() > 0:
                    # Check if the button is disabled
                    is_disabled = await next_button.evaluate("(button) => button.disabled")
                    print(f"Is Next button disabled: {is_disabled}")

                    if is_disabled:
                        print("Next button is disabled. Exiting pagination.")
                        break
                else:
                    print("Next button not found. Exiting pagination.")
                    break

                # Wait for the eui-icon-svg element to appear
                await page.wait_for_selector(next_icon_selector, timeout=20000)

                # Locate the icon
                next_icon = page.locator(next_icon_selector)

                # Debugging output
                print("Next icon count:", await next_icon.count())
                print("Next icon visible:", await next_icon.is_visible())

                # Click the icon if available
                if  await next_icon.count() > 0 and await next_icon.is_visible():
                    await next_icon.click()
                    print("Clicked the 'Next' icon.")
                    print("waiting for 30 sec to load next page")
                    await asyncio.sleep(30)

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
                # final_df.to_csv(f"{category}.csv", index=False)
                # print(f"Data saved to {category}.csv")

                for _, row in final_df.iterrows():
                    raw_deadline = (row.get("Deadline") or "").strip()
                    if not raw_deadline:
                        # Provide a default date (or decide to skip this record)
                        deadline_primary = datetime.today().date()  # or datetime.strptime("1900-01-01", "%Y-%m-%d").date()
                        deadline_secondary = None
                    else:
                        tokens = raw_deadline.split()
                        if len(tokens) >= 3:
                            # Parse the first date
                            try:
                                deadline_primary = format_date(raw_deadline.split(" ", 3)[0:3])  # Adjust as needed
                            except Exception as e:
                                # handle error, e.g. assign a default date
                                deadline_primary = datetime.today().date()
                            # Optionally process secondary if available...
                        else:
                            # If the record has an incomplete date string, assign a default or skip
                            deadline_primary = datetime.today().date()
                            deadline_secondary = None

                    #print(title)

                    try:
                        accepted_projects = int(row.get("Accepted Projects", 0))
                    except ValueError:
                        accepted_projects = 0

                    category_name = selected_categories[counter_for_menu]
                    category_id = await get_category_id(category_name)

                    # print(category_name)
                    # print(category_id)

                    print(formatted_opendate)

                    record = {
                        "identifier": row.get("Identifier"),
                        "title": row.get("Title"),
                        "action_type": row.get("Action"),
                        "budget": row.get("Budget"),
                        "funding_per_project": row.get("Funding Per Project"),
                        "deadline_primary": deadline_primary,  # e.g., "2021-10-06" or "06 OCT 2024"
                        "deadline_secondary": deadline_secondary,  # e.g., "14 APR 2024" or None
                        "opening_date": formatted_opendate,
                        "accepted_projects": row.get("Accepted Projects"),
                        "probability_rate": row.get("Probability Rate"),
                        "link": row.get("Link"),
                        "category_id": category_id,
                        "status": status
                    }

                    # print (record)
                    try:
                        await store_call(record)
                    except Exception as store_error:
                        print(f"Error during record extraction: {store_error}")

                # # --- JSON Saving Logic ---
                # results_json_path = "scraped_results.json"
                #
                # # Load existing data if file exists
                # if os.path.exists(results_json_path):
                #     try:
                #         with open(results_json_path, "r", encoding="utf-8") as file:
                #             existing_data = json.load(file)
                #     except json.JSONDecodeError:
                #         existing_data = []  # Reset if file is corrupted
                # else:
                #     existing_data = []
                #
                # # Append new data
                # new_data = final_df.to_dict(orient="records")  # Convert DataFrame to list of dicts
                # existing_data.extend(new_data)  # Merge new results
                #
                # # Save updated data back to file
                # with open(results_json_path, "w", encoding="utf-8") as file:
                #     json.dump(existing_data, file, indent=4)
                #
                # print(f"Results saved to {results_json_path}")

            counter_for_menu+=1

        os.remove("scraping_in_progress.json")
        # Close the browser
        await browser.close()