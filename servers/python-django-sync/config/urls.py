from django.urls import path

from config import views

urlpatterns = [
    path("io", views.io_endpoint),
    path("cpu", views.cpu_endpoint),
    path("db", views.db_endpoint),
]
