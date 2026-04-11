import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

thread_pool = ThreadPoolExecutor(max_workers=2)


def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


async def io_endpoint(request):
    await asyncio.sleep(0.2)
    return JSONResponse({"server": "python-freethreaded", "type": "io", "delay_ms": 200})


async def cpu_endpoint(request):
    result = fibonacci(38)
    return JSONResponse({
        "server": "python-freethreaded",
        "type": "cpu",
        "fibonacci": result,
        "gil_enabled": sys._is_gil_enabled(),
    })


async def cpu_mt_endpoint(request):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(thread_pool, fibonacci, 38)
    return JSONResponse({
        "server": "python-freethreaded",
        "type": "cpu-mt",
        "fibonacci": result,
        "gil_enabled": sys._is_gil_enabled(),
    })


async def status_endpoint(request):
    return JSONResponse({
        "server": "python-freethreaded",
        "python_version": sys.version,
        "gil_enabled": sys._is_gil_enabled(),
    })


app = Starlette(routes=[
    Route("/io", io_endpoint),
    Route("/cpu", cpu_endpoint),
    Route("/cpu-mt", cpu_mt_endpoint),
    Route("/status", status_endpoint),
])
