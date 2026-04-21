from django.contrib import admin
from .models import Client, Pipeline, Run, RawData, CleanedData

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'number')
    search_fields = ('name',)

@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ('name', 'id')

@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ('client', 'pipeline', 'status', 'step', 'updated_at')
    list_filter = ('status', 'step', 'client')
    readonly_fields = ('id', 'created_at', 'updated_at')

# These allow you to view the JSON payloads directly in the admin
admin.site.register(RawData)
admin.site.register(CleanedData)