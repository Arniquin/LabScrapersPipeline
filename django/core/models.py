import uuid
from django.db import models

class Pipeline(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(null=True, blank=True)
    number = models.CharField(max_length=20, null=True, blank=True)
    
    # The ManyToMany field is REMOVED. 
    # We will use the reverse relationship from PipelineInstance instead.

    def __str__(self):
        return self.name

class PipelineInstance(models.Model):
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('MANUAL', 'Manual'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alias = models.CharField(max_length=255, null=True, blank=True, help_text="Custom name for this instance")
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='pipeline_instances')
    pipeline = models.ForeignKey('Pipeline', on_delete=models.CASCADE, related_name='instances')
    pipeline_params = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='MANUAL')
    is_queued = models.BooleanField(default=False) # Marked by dispatcher for daily work
    last_run_at = models.DateTimeField(null=True, blank=True)

class Run(models.Model):
    STATUS_CHOICES = [
        ('RUNNING', 'Running'),
        ('FINISHED', 'Finished'),
        ('FAILED', 'Failed'),
    ]
    STEP_CHOICES = [
        ('DATA_RECOLLECTION', 'Data Recollection'),
        ('STORING_RAW_DATA', 'Storing Raw Data'),
        ('CLEANING_RAW_DATA', 'Cleaning Raw Data'),
        ('STORING_CLEANED_DATA', 'Storing Cleaned Data')
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(PipelineInstance, on_delete=models.CASCADE, related_name='runs')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='runs')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RUNNING')
    step = models.CharField(max_length=50, choices=STEP_CHOICES)
    last_log = models.TextField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ScraperSettings(models.Model):
    max_concurrent_instances = models.IntegerField(default=2)
    # Using integer hours (0-23) for simplicity in the dispatcher
    window_start_hour = models.IntegerField(default=9) # 9 AM
    window_end_hour = models.IntegerField(default=18)  # 6 PM

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

class RawData(models.Model):
    run = models.OneToOneField(Run, on_delete=models.CASCADE, related_name='raw_data')
    payload = models.JSONField()

class CleanedData(models.Model):
    run = models.OneToOneField(Run, on_delete=models.CASCADE, related_name='cleaned_data')
    payload = models.JSONField()