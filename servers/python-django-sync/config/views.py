import os
import time

import psycopg2
from psycopg2 import pool
from django.http import JsonResponse

DB_HOST = os.environ.get("DB_HOST", "postgres")
db_pool = psycopg2.pool.ThreadedConnectionPool(
    5, 20, host=DB_HOST, port=5432, dbname="bench", user="bench", password="bench"
)


def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def io_endpoint(request):
    time.sleep(0.2)
    return JsonResponse({"server": "django-sync", "type": "io", "delay_ms": 200})


def cpu_endpoint(request):
    result = fibonacci(38)
    return JsonResponse({"server": "django-sync", "type": "cpu", "fibonacci": result})


def db_endpoint(request):
    conn = db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_sleep(0.2)")
        cur.close()
    finally:
        db_pool.putconn(conn)
    return JsonResponse({"server": "django-sync", "type": "db", "delay_ms": 200})
