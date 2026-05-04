# django/pipelines_dashboard/urls.py
from django.urls import path
from . import views



urlpatterns = [
    path('', views.pipelines, name='pipelines'),
    path('load-pipelines/', views.load_pipelines, name='load_pipelines'),
    path('update-pipeline/<uuid:pipeline_id>/', views.update_pipeline, name='update_pipeline'),
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/add/', views.add_client, name='add_client'),
    path('clients/delete/<uuid:client_id>/', views.delete_client, name='delete_client'),
    path('clients/manage-pipeline/<uuid:client_id>/', views.update_client_pipelines, name='update_client_pipelines'),
    path('clients/toggle/<uuid:client_id>/', views.toggle_client, name='toggle_client'),
    path('clients/add-form/', views.client_add_form, name='client_add_form'),
]