import time

from asgiref.sync import sync_to_async
from django.http import JsonResponse


def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


async def io_endpoint(request):
    await sync_to_async(time.sleep)(0.2)
    return JsonResponse({"server": "django-async-orm", "type": "io", "delay_ms": 200})


async def cpu_endpoint(request):
    result = await sync_to_async(fibonacci)(38)
    return JsonResponse({"server": "django-async-orm", "type": "cpu", "fibonacci": result})
