import time

from fastapi import FastAPI

app = FastAPI()


def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


@app.get("/io")
def io_endpoint():
    time.sleep(0.2)
    return {"server": "fastapi-sync", "type": "io", "delay_ms": 200}


@app.get("/cpu")
def cpu_endpoint():
    result = fibonacci(38)
    return {"server": "fastapi-sync", "type": "cpu", "fibonacci": result}
