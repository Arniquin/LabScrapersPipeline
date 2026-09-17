from django.contrib import admin
from .models import (
    Client, Pipeline, Run, RawData, 
    CleanedData, PipelineInstance, ScraperSettings
)

# --- Inlines ---

class PipelineInstanceInline(admin.TabularInline):
    """Allows managing a client's instances directly from the Client page."""
    model = PipelineInstance
    extra = 0
    fields = ('alias', 'pipeline', 'is_active', 'frequency', 'last_run_at')
    readonly_fields = ('last_run_at',)

# --- Admin Classes ---

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'number')
    search_fields = ('name', 'email')
    inlines = [PipelineInstanceInline]

@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ('name', 'id')
    search_fields = ('name',)

@admin.register(PipelineInstance)
class PipelineInstanceAdmin(admin.ModelAdmin):
    list_display = ('alias', 'client', 'pipeline', 'frequency', 'is_active', 'is_queued', 'last_run_at')
    list_filter = ('is_active', 'frequency', 'is_queued', 'pipeline', 'client')
    list_editable = ('is_active', 'frequency')
    search_fields = ('alias', 'client__name', 'pipeline__name')
    readonly_fields = ('id', 'last_run_at')

@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ('id_short', 'instance_alias', 'client', 'status', 'step', 'updated_at')
    list_filter = ('status', 'step', 'client', 'pipeline')
    search_fields = ('id', 'client__name', 'pipeline__name', 'instance__alias')
    readonly_fields = ('id', 'instance', 'client', 'pipeline', 'created_at', 'updated_at')
    
    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = 'Run ID'

    def instance_alias(self, obj):
        return obj.instance.alias or obj.pipeline.name
    instance_alias.short_description = 'Instance'

@admin.register(ScraperSettings)
class ScraperSettingsAdmin(admin.ModelAdmin):
    list_display = ('max_concurrent_instances', 'window_start_hour', 'window_end_hour')
    
    def has_add_permission(self, request):
        # Prevents creating multiple settings objects
        return not ScraperSettings.objects.exists()

# --- Data Auditing ---

@admin.register(RawData)
class RawDataAdmin(admin.ModelAdmin):
    list_display = ('run', 'created_at_display')
    readonly_fields = ('run', 'payload')

    def created_at_display(self, obj):
        return obj.run.created_at
    created_at_display.short_description = 'Created At'

@admin.register(CleanedData)
class CleanedDataAdmin(admin.ModelAdmin):
    list_display = ('run', 'created_at_display')
    readonly_fields = ('run', 'payload')

    def created_at_display(self, obj):
        return obj.run.created_at
    created_at_display.short_description = 'Created At'