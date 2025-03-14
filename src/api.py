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
from starlette.responses import HTMLResponse
from scraper import scrape_eu_portal
import sys
import os
from urllib.parse import urlencode
import json
from database import fetch_all_calls, fetch_calls_by_filters, get_pool

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
    # results_json_path = "scraped_results.json"
    # progress_flag = "scraping_in_progress.json"
    #
    # if os.path.exists(progress_flag):
    #     return templates.TemplateResponse("loading.html",
    #                                       {"request": request, "message": "Scraping still in progress..."})

    data = await fetch_all_calls()

    return templates.TemplateResponse("results.html", {"request": request, "data": data})

@app.get("/search", response_class=HTMLResponse)
async def search_calls(
    request: Request,
    keyword: str = "",
    status: str = "all",
    probability: str = "all"
):
    data = await fetch_calls_by_filters(keyword, status, probability)
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
async def export_excel(
    keyword: str = "",
    statuses: str = "",  # comma-separated statuses, e.g., "open,closed"
    probability: str = "all"
):
    """
    Generate an Excel file from the filtered results in the DB and provide it for download.
    The filters (keyword, statuses, probability) should match those currently used on-screen.
    """
    output_excel_path = "scraped_results.xlsx"

    # Build a dynamic SQL query based on the filters.
    pool_obj = await get_pool()
    async with pool_obj.acquire() as conn:
        query = "SELECT * FROM scraped_calls WHERE 1=1"
        params = []
        param_index = 1

        if keyword:
            query += f" AND title ILIKE '%' || ${param_index} || '%'"
            params.append(keyword)
            param_index += 1

        # If statuses are provided (as a comma-separated string), filter on them.
        if statuses:
            # Convert comma-separated string into a list (and normalize to lower-case)
            status_list = [s.strip().lower() for s in statuses.split(",") if s.strip()]
            # Use the PostgreSQL ANY operator
            query += f" AND lower(status) = ANY(${param_index})"
            params.append(status_list)
            param_index += 1

        # If probability is provided and not "all", add that filter.
        if probability and probability.lower() != "all":
            query += f" AND lower(probability_rate) = ${param_index}"
            params.append(probability.lower())
            param_index += 1

        # Execute the query.
        rows = await conn.fetch(query, *params)
        data = [dict(row) for row in rows]

    if not data:
        return {"error": "No data found"}

    # Group results by category.
    grouped_data = {}
    for entry in data:
        # Use your existing function to extract the group name from the identifier.
        identifier = entry.get("identifier", "Unknown")
        category_group = extract_group_name(identifier)
        if category_group not in grouped_data:
            grouped_data[category_group] = []
        grouped_data[category_group].append(entry)

    # Write grouped data to an Excel file with separate sheets.
    with pd.ExcelWriter(output_excel_path) as writer:
        for category, entries in grouped_data.items():
            df = pd.DataFrame(entries)
            # Limit sheet name length if needed.
            sheet_name = category[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    # Apply color formatting to the "Probability Rate" column.
    wb = load_workbook(output_excel_path)
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        headers = [cell.value for cell in sheet[1]]  # first row as headers
        if "Probability Rate" in headers:
            probability_col_index = headers.index("Probability Rate") + 1  # 1-based index
            for row in range(2, sheet.max_row + 1):
                cell = sheet.cell(row=row, column=probability_col_index)
                if cell.value == "Low":
                    cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6", fill_type="solid")
                elif cell.value == "Medium":
                    cell.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
                elif cell.value == "High":
                    cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
    wb.save(output_excel_path)
    print(f"✅ Excel file created successfully: {output_excel_path}")

    return FileResponse(
        output_excel_path,
        filename="scraped_results.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Run with: uvicorn api:app --host 127.0.0.1 --port 5000 (DONT USE --reload)
