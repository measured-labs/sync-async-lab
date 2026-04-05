import asyncio

from fastapi import FastAPI

app = FastAPI()


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
