import asyncpg
import os
from datetime import datetime

# Replace with your actual PostgreSQL connection URL or set DATABASE_URL in your environment.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:bruhm0m3nt&@localhost:5432/postgres")

# Global connection pool variable
pool: asyncpg.Pool = None

async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    return pool

async def get_category_id(category_name: str) -> int:
    pool_obj = await get_pool()
    async with pool_obj.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM Categories WHERE name = $1", category_name)
        if row:
            return row["id"]
        else:
            raise Exception(f"Category '{category_name}' not found.")


async def store_category(name: str, description: str = "No Description") -> int:
    """
    Inserts (or updates) a category in the Categories table.
    Assumes a Categories table defined as:
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      description TEXT
    """
    pool_obj = await get_pool()
    async with pool_obj.acquire() as conn:
        # Upsert the category: if a category with the given name already exists,
        # update its description; otherwise, insert a new row.
        await conn.execute("""
            INSERT INTO Categories (name, description)
            VALUES ($1, $2)
            ON CONFLICT (name) DO NOTHING
            
            --ON CONFLICT (name) DO UPDATE
              --SET description = EXCLUDED.description;
        """, name, description)


async def store_call(data: dict):
    """
    Inserts or updates a scraped call record into the database.
    Expected keys:
      - identifier, title, action_type, budget, funding_per_project,
        deadline_primary, deadline_secondary, opening_date,
        accepted_projects, probability_rate, link, category_id
    """
    # We assume deadlines and opening_date are already stored as text.
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO scraped_calls (
                identifier, title, action_type, budget, funding_per_project,
                deadline_primary, deadline_secondary, opening_date,
                accepted_projects, probability_rate, link, category_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
                link = EXCLUDED.link,
                category_id = EXCLUDED.category_id
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
        data.get("link"),
        data.get("category_id")
        )


async def fetch_all_categories():
    """
    Fetch all stored call records from the database.
    Returns a list of dictionaries.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM categories")
        return [dict(row) for row in rows]


async def fetch_all_calls():
    pool_obj = await get_pool()
    async with pool_obj.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM scraped_calls")
            rows = await cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]

