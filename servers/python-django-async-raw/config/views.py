import asyncio

from django.http import JsonResponse


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
