from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, FileResponse
from typing import List
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
import json

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
async def home(request: Request, closed: bool = None):
    """
    Step 1: Ask if the user wants closed calls.
    Step 2: Show loading page while fetching categories.
    """
    if closed is None:
        return templates.TemplateResponse("choose_closed.html", {"request": request})

    return RedirectResponse(url=f"/fetching_calls_loading?redirect_url=/fetch-categories?closed={closed}")


@app.get("/fetch-categories")
async def fetch_categories(request: Request, closed: bool):
    """
    Fetch categories asynchronously, then redirect to home with data.
    """
    categories = await scrape_eu_portal(get_categories_only=True, closed_option=closed)

    # Store categories in session (or temp storage)
    request.session["categories"] = categories
    request.session["closed"] = closed

    # Redirect back to home when done
    return RedirectResponse(url="/categories")

@app.get("/categories")
async def categories_page(request: Request):
    """
    Load the category selection page with stored categories.
    """
    categories = request.session.get("categories", [])
    closed = request.session.get("closed", False)

    return templates.TemplateResponse("home.html", {"request": request, "categories": categories, "closed": closed})

@app.get("/loading")
async def loading_page(request: Request, redirect_url: str):
    """
    Displays a loading screen and redirects to the specified URL after a delay.
    """

    progress_flag = "scraping_in_progress.json"

    wait_interval = 10

    if not os.path.exists(progress_flag):  # ✅ Only continue when flag is removed
        return RedirectResponse(url=redirect_url)

    await asyncio.sleep(wait_interval)

    return templates.TemplateResponse("loading.html", {"request": request, "redirect_url": redirect_url})


@app.get("/fetching_calls_loading")
async def fetching_calls_loading(request: Request, redirect_url: str):

    return templates.TemplateResponse("loading_after_closed_choice.html", {"request": request, "redirect_url": redirect_url})
@app.post("/scrape")
async def scrape_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    categories: List[str] = Form(...),
    closed: bool = Form(False)
):
    """
    Starts scraping for selected categories in the background.
    """
    background_tasks.add_task(scrape_eu_portal, closed_option=closed, desired_category=categories)

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

@app.get("/export-excel")
async def export_excel():
    """
    Generate an Excel file from the scraped results and provide it for download.
    """
    results_json_path = "scraped_results.json"
    output_excel_path = "scraped_results.xlsx"

    # Read JSON file
    try:
        with open(results_json_path, "r", encoding="utf-8") as file:
            data = pd.read_json(file)
    except FileNotFoundError:
        return {"error": "No scraped data available"}

    # Convert JSON to Excel
    data.to_excel(output_excel_path, index=False)

    # Apply coloring to the "Probability Rate" column
    wb = load_workbook(output_excel_path)
    sheet = wb.active  # Get the active sheet (assuming one sheet)

    # Find the "Probability Rate" column
    headers = [cell.value for cell in sheet[1]]  # Get the first row (header)

    if "Probability Rate" in headers:
        probability_col_index = headers.index("Probability Rate") + 1  # Convert to 1-based index

        # Apply color formatting based on the values
        for row in range(2, sheet.max_row + 1):  # Skip header row
            cell = sheet.cell(row=row, column=probability_col_index)
            if cell.value == "Low":
                cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6", fill_type="solid")  # Light blue
            elif cell.value == "Medium":
                cell.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")  # Yellow
            elif cell.value == "High":
                cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")  # Green

    # Save the workbook with color formatting
    wb.save(output_excel_path)

    # Return the Excel file as a response
    return FileResponse(output_excel_path, filename="scraped_results.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Run with: uvicorn api:app (DONT USE --reload)
