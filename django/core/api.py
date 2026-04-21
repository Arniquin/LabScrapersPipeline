import uuid
from typing import Optional
from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from .models import Client, Pipeline, Run, RawData, CleanedData
from .auth import InternalAuth

api = NinjaAPI(auth=InternalAuth())

# --- Schemas ---
class StartRunSchema(Schema):
    client_name: str
    pipeline_name: str
    initial_step: str = "DATA_RECOLLECTION"

class UpdateRunSchema(Schema):
    status: Optional[str] = None
    step: Optional[str] = None
    last_log: Optional[str] = None

class DataPayloadSchema(Schema):
    payload: dict

# --- Endpoints ---

@api.post("/runs/start")
def start_run(request, data: StartRunSchema):
    client, _ = Client.objects.get_or_create(name=data.client_name)
    pipeline, _ = Pipeline.objects.get_or_create(name=data.pipeline_name)
    
    run = Run.objects.create(
        client=client,
        pipeline=pipeline,
        status='RUNNING',
        step=data.initial_step,
        last_log=f"Pipeline {data.client_name}:{data.pipeline_name} STARTED"
    )
    return {"run_id": str(run.id)}

@api.patch("/runs/{run_id}/update")
def update_run(request, run_id: uuid.UUID, data: UpdateRunSchema):
    run = get_object_or_404(Run, id=run_id)
    if data.status: run.status = data.status
    if data.step: run.step = data.step
    if data.last_log: run.last_log = data.last_log
    run.save()
    return {"success": True}

@api.post("/runs/{run_id}/raw")
def store_raw_data(request, run_id: uuid.UUID, data: DataPayloadSchema):
    run = get_object_or_404(Run, id=run_id)
    RawData.objects.update_or_create(run=run, defaults={'payload': data.payload})
    run.step = 'STORING_RAW_DATA'
    run.last_log = "Raw data successfully persisted."
    run.save()
    return {"success": True}

@api.post("/runs/{run_id}/cleaned")
def store_cleaned_data(request, run_id: uuid.UUID, data: DataPayloadSchema):
    run = get_object_or_404(Run, id=run_id)
    CleanedData.objects.update_or_create(run=run, defaults={'payload': data.payload})
    run.step = 'STORING_CLEANED_DATA'
    run.status = 'FINISHED'
    run.last_log = "Pipeline completed successfully."
    run.save()
    return {"success": True}