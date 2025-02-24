import asyncpg
import os
from datetime import datetime

# Replace with your actual PostgreSQL connection URL or set DATABASE_URL in your environment.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:[password]@localhost:5432/postgres")

# Global connection pool variable
pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    """
    Lazily initializes and returns the global connection pool.
    """
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    return pool


async def store_call(data: dict):
    """
    Inserts or updates a scraped call record into the database.
    Expected keys:
      - identifier, title, action_type, budget, funding_per_project,
        deadline_primary, deadline_secondary, opening_date,
        accepted_projects, probability_rate, link
    """
    # We assume deadlines and opening_date are already stored as text.
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO scraped_calls (
                identifier, title, action_type, budget, funding_per_project,
                deadline_primary, deadline_secondary, opening_date,
                accepted_projects, probability_rate, link
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (identifier) DO UPDATE
            SET 
                title = EXCLUDED.title,
                action_type = EXCLUDED.action_type,
                budget = EXCLUDED.budget,
                funding_per_project = EXCLUDED.funding_per_project,
                deadline_primary = EXCLUDED.deadline_primary,
                deadline_secondary = EXCLUDED.deadline_secondary,
                opening_date = EXCLUDED.opening_date,
                accepted_projects = EXCLUDED.accepted_projects,
                probability_rate = EXCLUDED.probability_rate,
                link = EXCLUDED.link
        """,
        data.get("identifier"),
        data.get("title"),
        data.get("action_type"),
        data.get("budget"),
        data.get("funding_per_project"),
        data.get("deadline_primary"),
        data.get("deadline_secondary"),
        data.get("opening_date"),
        data.get("accepted_projects"),
        data.get("probability_rate"),
        data.get("link")
        )



async def fetch_all_calls():
    """
    Fetch all stored call records from the database.
    Returns a list of dictionaries.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM scraped_calls")
        return [dict(row) for row in rows]
