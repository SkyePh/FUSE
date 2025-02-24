from fastapi import FastAPI, Request, Form, BackgroundTasks, Query
from fastapi.responses import RedirectResponse, FileResponse
from contextlib import asynccontextmanager
from typing import List, Optional
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
import asyncio
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from scraper import scrape_eu_portal
import sys
import os
from urllib.parse import urlencode
import json
from database import fetch_all_calls

# Windows-specific fix for Playwright subprocess execution
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="secretkey")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Serve static files (if needed)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """ Redirect root to home """
    return RedirectResponse(url="/home")

from fastapi.responses import RedirectResponse

@app.get("/home")
async def home(request: Request):
    """
    Step 1: Ask if the user wants closed calls.
    Step 2: Show loading page while fetching categories.
    """

    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/choose_closed")
async def choose_closed(request: Request):
    """
    Ask user whether they want closed calls.
    """
    return templates.TemplateResponse("choose_closed.html", {"request": request})


@app.post("/fetch-categories")
async def fetch_categories(
    request: Request,
    closed: str = Form("false"),
    forthcoming: str = Form("false"),
    open_: str = Form("false", alias="open"),
    keyword: Optional[str] = Form("")
):
    """
    Fetch categories and pass them directly to /categories via query parameters.
    """

    print(f"📥 Raw Data from Form Submission → Closed: {closed}, Forthcoming: {forthcoming}, Open: {open_}")

    # Convert "true"/"false" strings to actual booleans
    closed_bool = closed.lower() == "true"
    forthcoming_bool = forthcoming.lower() == "true"
    open_bool = open_.lower() == "true"

    print(f"✅ Converted Bools → Closed: {closed_bool}, Forthcoming: {forthcoming_bool}, Open: {open_bool}")

    # Fetch categories from scraper
    categories = await scrape_eu_portal(
        get_categories_only=True,
        closed_option=closed_bool,
        forthcoming_option=forthcoming_bool,
        open_option=open_bool,
        keyword=keyword
    )

    print("✅ Categories Retrieved from Scraper:", categories)

    return templates.TemplateResponse("options.html", {
        "request": request,
        "categories": categories,
        "closed": closed_bool,
        "forthcoming": forthcoming_bool,
        "open": open_bool
    })


@app.get("/categories")
async def categories_page(
    request: Request,
    categories: List[str] = Query([]),
    closed: bool = Query(False),
    forthcoming: bool = Query(False),
    open_: bool = Query(False, alias="open")
):
    """
    Load category selection page using query parameters.
    """
    print("🟠 Categories from Query Params:", categories)
    print(f"Filters - Closed: {closed}, Forthcoming: {forthcoming}, Open: {open_}")

    return templates.TemplateResponse("options.html", {
        "request": request,
        "categories": categories,
        "closed": closed,
        "forthcoming": forthcoming,
        "open": open_
    })

@app.get("/loading")
async def loading_page(request: Request, redirect_url: str):
    """
    Displays a loading screen and redirects to the specified URL after a delay.
    """

    progress_flag = "scraping_in_progress.json"

    #wait_interval = 3

    if not os.path.exists(progress_flag):
        return RedirectResponse(url=redirect_url)

    #await asyncio.sleep(wait_interval)

    return templates.TemplateResponse("loading.html", {"request": request, "redirect_url": redirect_url})


@app.post("/scrape")
async def scrape_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    categories: List[str] = Form(...),
    closed: bool = Form(...),
    forthcoming: bool = Form(...),
    open_: bool = Form(..., alias="open")
):
    """
    Starts scraping for selected categories in the background with filtering options.
    """
    print("🟠 Scrape Endpoint Called")
    print(f"Selected Categories: {categories}")
    print(f"Filters - Closed: {closed}, Forthcoming: {forthcoming}, Open: {open_}")

    # Start the scraper with the selected filters
    background_tasks.add_task(
        scrape_eu_portal,
        closed_option=closed,
        forthcoming_option=forthcoming,
        open_option=open_,
        desired_category=categories
    )

    return RedirectResponse(url="/loading?redirect_url=/results", status_code=303)




@app.get("/results")
async def get_results(request: Request):
    """
    Fetches the scraped results and displays them in an HTML page.
    """
    results_json_path = "scraped_results.json"
    progress_flag = "scraping_in_progress.json"

    if os.path.exists(progress_flag):
        return templates.TemplateResponse("loading.html",
                                          {"request": request, "message": "Scraping still in progress..."})

    # Read the JSON file
    try:
        with open(results_json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []  # Return empty list if no results found

    return templates.TemplateResponse("results.html", {"request": request, "data": data})


def extract_group_name(identifier):
    """Extracts the category group from an identifier (e.g., 'HORIZON-CL5-D4' -> 'CL5')."""
    parts = identifier.split('-')
    if parts[0] == "HORIZON" and len(parts) > 1:
        return parts[1]  # Returns 'CL5' from 'HORIZON-CL5-D4'
    elif len(parts) > 1:
        return parts[0]  # Returns 'JU' or another top-level group
    else:
        return identifier  # Fallback for unknown formats


@app.get("/export-excel")
async def export_excel():
    """
    Generate an Excel file from the scraped results and provide it for download.
    """
    results_json_path = "scraped_results.json"
    output_excel_path = "scraped_results.xlsx"

    # Read JSON file
    if not os.path.exists(results_json_path):
        return {"error": "No scraped data available"}

    with open(results_json_path, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON data"}

    if not data:
        return {"error": "No data found"}

    # Group results by category
    grouped_data = {}

    for entry in data:
        identifier = entry.get("Identifier", "Unknown")
        category_group = extract_group_name(identifier)

        if category_group not in grouped_data:
            grouped_data[category_group] = []

        grouped_data[category_group].append(entry)

    # Write data to an Excel file with separate sheets
    with pd.ExcelWriter(output_excel_path) as writer:
        for category, entries in grouped_data.items():
            df = pd.DataFrame(entries)
            df.to_excel(writer, sheet_name=category, index=False)

    # Apply color formatting to the "Probability Rate" column
    wb = load_workbook(output_excel_path)

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        headers = [cell.value for cell in sheet[1]]  # First row as headers

        if "Probability Rate" in headers:
            probability_col_index = headers.index("Probability Rate") + 1  # Convert to 1-based index

            # Apply color formatting based on probability rate values
            for row in range(2, sheet.max_row + 1):  # Skip header row
                cell = sheet.cell(row=row, column=probability_col_index)
                if cell.value == "Low":
                    cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6", fill_type="solid")  # Light blue
                elif cell.value == "Medium":
                    cell.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")  # Yellow
                elif cell.value == "High":
                    cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")  # Green

    # Save the workbook with formatting applied
    wb.save(output_excel_path)

    print(f"✅ Excel file created successfully: {output_excel_path}")

    # Return the Excel file as a response for download
    return FileResponse(output_excel_path, filename="scraped_results.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Run with: uvicorn api:app (DONT USE --reload)
