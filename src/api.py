from fastapi import FastAPI, BackgroundTasks
from typing import List
import asyncio
from scraper import scrape_eu_portal  # Import your Playwright scraper
import sys

# Windows-specific fix for Playwright subprocess execution
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "FastAPI is working!"}


@app.post("/scrape")
async def scrape_endpoint(categories: List[int], closed: bool, background_tasks: BackgroundTasks):
    background_tasks.add_task(scrape_eu_portal, closed, categories)
    return {"message": "Scraping started in the background."}


# Run with: uvicorn api:app --reload
