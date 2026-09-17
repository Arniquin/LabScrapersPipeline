# django/pipelines_dashboard/urls.py
from django.urls import path
from . import views



urlpatterns = [
    # Pipelines
    path('', views.pipelines, name='pipelines'),
    path('load-pipelines/', views.load_pipelines, name='load_pipelines'),
    path('update-pipeline/<uuid:pipeline_id>/', views.update_pipeline, name='update_pipeline'),
    path('upload-pipeline-script/<uuid:pipeline_id>/', views.upload_pipeline_script, name='upload_pipeline_script'),
    path('upload-new-pipeline/', views.upload_new_pipeline, name='upload_new_pipeline'),
    # Clients
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/add/', views.add_client, name='add_client'),
    path('clients/delete/<uuid:client_id>/', views.delete_client, name='delete_client'),
    path('clients/manage-pipeline/<uuid:client_id>/', views.update_client_pipelines, name='update_client_pipelines'),
    path('clients/toggle/<uuid:client_id>/', views.toggle_client, name='toggle_client'),
    path('clients/add-form/', views.client_add_form, name='client_add_form'),
    # pipelines_dashboard/urls.py
    path('instance/params/edit/<uuid:instance_id>/', views.edit_instance_params, name='edit_instance_params'),
    path('instance/params/update/<uuid:instance_id>/', views.update_instance_params, name='update_instance_params'),
    # Scheduler
    path('scheduler/', views.scheduler_view, name='scheduler_view'),
    path('scheduler/update-settings/', views.update_scheduler_settings, name='update_scheduler_settings'),
    path('scheduler/frequency/<uuid:instance_id>/', views.update_instance_frequency, name='update_instance_frequency'),
    path('scheduler/toggle/<uuid:instance_id>/', views.toggle_instance_active, name='toggle_instance_active'),
    path('scheduler/run/<uuid:instance_id>/', views.run_instance_manual, name='run_instance_manual'),
    # Runs
    # pipelines_dashboard/urls.py
    path('runs/', views.runs_view, name='runs_view'),
]