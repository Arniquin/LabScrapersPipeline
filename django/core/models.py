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
    
    # Many-to-Many relationship added here
    pipelines = models.ManyToManyField(
        Pipeline, 
        related_name='clients', 
        blank=True
    )

    def __str__(self):
        return self.name

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
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='runs')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RUNNING')
    step = models.CharField(max_length=50, choices=STEP_CHOICES)
    last_log = models.TextField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class RawData(models.Model):
    run = models.OneToOneField(Run, on_delete=models.CASCADE, related_name='raw_data')
    payload = models.JSONField()

class CleanedData(models.Model):
    run = models.OneToOneField(Run, on_delete=models.CASCADE, related_name='cleaned_data')
    payload = models.JSONField()