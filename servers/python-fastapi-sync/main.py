import os
import time

import psycopg2
from psycopg2 import pool
from fastapi import FastAPI

app = FastAPI()

DB_HOST = os.environ.get("DB_HOST", "postgres")
db_pool = None


@app.on_event("startup")
def startup():
    global db_pool
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        5, 20, host=DB_HOST, port=5432, dbname="bench", user="bench", password="bench"
    )


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


@app.get("/db")
def db_endpoint():
    conn = db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_sleep(0.2)")
        cur.close()
    finally:
        db_pool.putconn(conn)
    return {"server": "fastapi-sync", "type": "db", "delay_ms": 200}
