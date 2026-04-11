import asyncio
import os
from concurrent.futures import ProcessPoolExecutor

import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

DB_HOST = os.environ.get("DB_HOST", "postgres")
db_pool = None
process_pool = None


@app.on_event("startup")
async def startup():
    global db_pool, process_pool
    pool_size = int(os.environ.get("POOL_SIZE", "20"))
    db_pool = await asyncpg.create_pool(
        host=DB_HOST, port=5432, database="bench", user="bench", password="bench",
        min_size=min(5, pool_size), max_size=pool_size
    )
    process_pool = ProcessPoolExecutor(max_workers=2)


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


@app.get("/cpu-mp")
async def cpu_mp_endpoint():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(process_pool, fibonacci, 38)
    return {"server": "fastapi-async", "type": "cpu-mp", "fibonacci": result}


@app.get("/db")
async def db_endpoint():
    async with db_pool.acquire() as conn:
        await conn.fetchval("SELECT pg_sleep(0.2)")
    return {"server": "fastapi-async", "type": "db", "delay_ms": 200}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(data)
    except WebSocketDisconnect:
        pass
