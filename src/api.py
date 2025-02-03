from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse
from typing import List
import asyncio
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from scraper import scrape_eu_portal
import sys
import json

# Windows-specific fix for Playwright subprocess execution
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Serve static files (if needed)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """ Redirect root to home """
    return RedirectResponse(url="/home")

@app.get("/home")
async def home(request: Request, closed: bool = None):
    """
    Step 1: Ask if the user wants closed calls.
    Step 2: Once chosen, show loading and fetch categories.
    """
    if closed is None:
        # Show the first page where the user selects if they want closed calls
        return templates.TemplateResponse("choose_closed.html", {"request": request})

    # If closed option is provided, start fetching categories
    categories = await scrape_eu_portal(get_categories_only=True, closed_option=closed)

    # Show the category selection page after loading
    return templates.TemplateResponse("home.html", {"request": request, "categories": categories, "closed": closed})


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

    return templates.TemplateResponse("loading.html", {"request": request, "categories": categories})


@app.get("/results")
async def get_results(request: Request):
    """
    Fetches the scraped results and displays them in an HTML page.
    """
    results_json_path = "scraped_results.json"

    # Read the JSON file
    try:
        with open(results_json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []  # Return empty list if no results found

    return templates.TemplateResponse("results.html", {"request": request, "data": data})


# Run with: uvicorn api:app (DONT USE --reload)
