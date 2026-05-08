import json
import subprocess
from pathlib import Path
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import PipelineInstance, Run, ScraperSettings, Client, Pipeline

# ----------------------------------------------------------------------------------
# 1. DAILY PLANNER
# Schedule: Run once a day at 00:00 (Midnight)
# ----------------------------------------------------------------------------------
@shared_task(name="daily_planner")
def daily_planner():
    """Checks frequencies and marks instances that need to run today."""
    now = timezone.now()
    # Fetch all active instances that aren't set to Manual
    instances = PipelineInstance.objects.filter(is_active=True).exclude(frequency='MANUAL')
    
    queued_count = 0
    for inst in instances:
        is_due = False
        
        if inst.frequency == 'DAILY':
            is_due = True
        elif inst.frequency == 'WEEKLY':
            # Run if never run before, or if last run was > 7 days ago
            if not inst.last_run_at or inst.last_run_at < now - timedelta(days=7):
                is_due = True
        elif inst.frequency == 'MONTHLY':
            # Run if never run before, or if last run was > 30 days ago
            if not inst.last_run_at or inst.last_run_at < now - timedelta(days=30):
                is_due = True
                
        if is_due:
            inst.is_queued = True
            inst.save()
            queued_count += 1
            
    return f"Planner finished. {queued_count} instances queued for today."

# ----------------------------------------------------------------------------------
# 2. HEARTBEAT DISPATCHER
# Schedule: Run every 1-5 minutes
# ----------------------------------------------------------------------------------
@shared_task(name="heartbeat_dispatcher")
def heartbeat_dispatcher():
    """Checks concurrency limits and time windows to trigger execution."""
    conf = ScraperSettings.get_settings()
    now = timezone.now()
    
    # Check Time Window Guard
    # (Note: Uses UTC or Server Time depending on your Django settings)
    if not (conf.window_start_hour <= now.hour < conf.window_end_hour):
        return f"Idle: Outside window ({conf.window_start_hour}:00 - {conf.window_end_hour}:00)"

    # Check Concurrency Guard (Ryzen 2700x Protection)
    running_count = Run.objects.filter(status='RUNNING').count()
    if running_count >= conf.max_concurrent_instances:
        return f"Idle: At max concurrency ({running_count}/{conf.max_concurrent_instances})"

    # Calculate available slots
    slots_available = conf.max_concurrent_instances - running_count
    
    # Pick the next instances that were marked by the planner
    to_run = PipelineInstance.objects.filter(
        is_active=True, 
        is_queued=True
    ).order_by('last_run_at')[:slots_available]

    for instance in to_run:
        # Mark as no longer queued to prevent double-triggering
        instance.is_queued = False
        instance.save()
        
        # Trigger the actual worker task
        run_pipeline_instance.delay(instance.id)

    return f"Dispatched {to_run.count()} instances."

# ----------------------------------------------------------------------------------
# 3. WORKER EXECUTION
# ----------------------------------------------------------------------------------
@shared_task(bind=True, name="run_pipeline_instance")
def run_pipeline_instance(self, instance_id):
    """The heavy lifter: Runs the Python script via subprocess."""
    instance = PipelineInstance.objects.get(id=instance_id)
    
    # Create the Run record (Denormalizing Client/Pipeline for fast querying)
    run = Run.objects.create(
        instance=instance,
        client=instance.client,
        pipeline=instance.pipeline,
        status='RUNNING',
        step='DATA_RECOLLECTION',
        last_log = 'Pipeline started'
    )
    
    # Prepare Paths
    base_path = Path("./jupyter_data/scraper_pipelines")
    script_path = base_path / 'pipelines_scripts' / f"{instance.pipeline.name}.py"
    
    if not script_path.exists():
        run.status = 'FAILED'
        run.last_log = f"Error: Script not found at {script_path}. Did you click 'Update' on the pipeline?"
        run.save()
        return "Failed: Missing Script"

    try:
        # Prepare parameters for the script
        params_str = json.dumps(instance.pipeline_params)
        
        # Execute the script
        # We use str(script_path) because subprocess needs a string path
        result = subprocess.run(
            ["python3", str(script_path), str(run.id) , params_str],
            capture_output=True,
            text=True,
            timeout=3600 # 1 hour safety timeout
        )
        
        if result.returncode == 0:
            run.status = 'FINISHED'
            run.last_log = result.stdout
            instance.last_run_at = timezone.now()
        else:
            run.status = 'FAILED'
            run.last_log = result.stderr
            return f"Failed:{result.stderr}"
            
    except subprocess.TimeoutExpired:
        run.status = 'FAILED'
        run.last_log = "Error: Task timed out after 1 hour."
        return f"Failed:{result.stderr}"
    except Exception as e:
        run.status = 'FAILED'
        run.last_log = f"System Error: {str(e)}"
        return f"Failed:{result.stderr}"
    
    finally:
        run.save()
        instance.save()
        
    return f"Finished instance {instance.pipeline.name} for {instance.client.name}"