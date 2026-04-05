import json
import time

from django.http import JsonResponse


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
