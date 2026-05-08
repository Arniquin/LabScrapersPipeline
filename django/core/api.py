import uuid
from typing import Optional
from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from core.models import Client, Pipeline, Run, RawData, CleanedData, PipelineInstance
from .auth import InternalAuth

# Initialize the API with your internal secret authentication
api = NinjaAPI(auth=InternalAuth())

# --- Schemas ---

class StartRunSchema(Schema):
    """Requires an instance_id to correctly link the Run to its configuration."""
    instance_id: uuid.UUID
    initial_step: str = "DATA_RECOLLECTION"

class UpdateRunSchema(Schema):
    """Optional fields for incremental updates during scraper execution."""
    status: Optional[str] = None
    step: Optional[str] = None
    last_log: Optional[str] = None

class DataPayloadSchema(Schema):
    """Standard wrapper for JSON data blobs."""
    payload: dict

# --- Endpoints ---

@api.post("/runs/start")
def start_run(request, data: StartRunSchema):
    """
    Initiates a new Run entry. 
    Automatically pulls the Client and Pipeline from the associated Instance.
    """
    instance = get_object_or_404(PipelineInstance, id=data.instance_id)
    
    run = Run.objects.create(
        instance=instance,
        client=instance.client,
        pipeline=instance.pipeline,
        status='RUNNING',
        step=data.initial_step,
        last_log=f"Pipeline execution for '{instance.alias or instance.pipeline.name}' started."
    )
    return {"run_id": str(run.id)}

@api.patch("/runs/{run_id}/update")
def update_run(request, run_id: uuid.UUID, data: UpdateRunSchema):
    """Updates status, current step, or log messages for an active run."""
    run = get_object_or_404(Run, id=run_id)
    
    if data.status: 
        run.status = data.status
    if data.step: 
        run.step = data.step
    if data.last_log: 
        run.last_log = data.last_log
        
    run.save()
    return {"success": True}

@api.post("/runs/{run_id}/raw")
def store_raw_data(request, run_id: uuid.UUID, data: DataPayloadSchema):
    """Persists raw JSON data and moves the run to the STORING_RAW_DATA step."""
    run = get_object_or_404(Run, id=run_id)
    
    RawData.objects.update_or_create(
        run=run, 
        defaults={'payload': data.payload}
    )
    
    run.step = 'STORING_RAW_DATA'
    run.last_log = "Raw data successfully persisted to database."
    run.save()
    return {"success": True}

@api.post("/runs/{run_id}/cleaned")
def store_cleaned_data(request, run_id: uuid.UUID, data: DataPayloadSchema):
    """
    Persists cleaned JSON data.
    Automatically marks the run as FINISHED and sets the final step.
    """
    run = get_object_or_404(Run, id=run_id)
    
    CleanedData.objects.update_or_create(
        run=run, 
        defaults={'payload': data.payload}
    )
    
    run.step = 'STORING_CLEANED_DATA'
    run.status = 'FINISHED'
    run.last_log = "Pipeline completed successfully. Data cleaned and stored."
    run.save()
    return {"success": True}