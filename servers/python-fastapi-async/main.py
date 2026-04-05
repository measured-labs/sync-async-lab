import asyncio
import os

import asyncpg
from fastapi import FastAPI

app = FastAPI()

DB_HOST = os.environ.get("DB_HOST", "postgres")
db_pool = None


@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=DB_HOST, port=5432, database="bench", user="bench", password="bench",
        min_size=5, max_size=20
    )


def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


@app.get("/io")
async def io_endpoint():
    await asyncio.sleep(0.2)
    return {"server": "fastapi-async", "type": "io", "delay_ms": 200}


@app.get("/cpu")
async def cpu_endpoint():
    result = fibonacci(38)
    return {"server": "fastapi-async", "type": "cpu", "fibonacci": result}


@app.get("/db")
async def db_endpoint():
    async with db_pool.acquire() as conn:
        await conn.fetchval("SELECT pg_sleep(0.2)")
    return {"server": "fastapi-async", "type": "db", "delay_ms": 200}
