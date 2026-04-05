import asyncio
import os

import asyncpg
from django.http import JsonResponse

DB_HOST = os.environ.get("DB_HOST", "postgres")
db_pool = None


async def get_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(
            host=DB_HOST, port=5432, database="bench", user="bench", password="bench",
            min_size=5, max_size=20
        )
    return db_pool


def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


async def io_endpoint(request):
    await asyncio.sleep(0.2)
    return JsonResponse({"server": "django-async-raw", "type": "io", "delay_ms": 200})


async def cpu_endpoint(request):
    result = fibonacci(38)
    return JsonResponse({"server": "django-async-raw", "type": "cpu", "fibonacci": result})


async def db_endpoint(request):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT pg_sleep(0.2)")
    return JsonResponse({"server": "django-async-raw", "type": "db", "delay_ms": 200})
