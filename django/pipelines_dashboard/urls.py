# django/dashboard/urls.py
from django.urls import path
from .views import pipeline_dashboard

urlpatterns = [
    path('', pipeline_dashboard, name='index'),
]