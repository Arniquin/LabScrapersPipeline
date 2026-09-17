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
    """Checks frequencies and creates Run entries for instances that need to run today."""
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
            # Create a Run with status 'QUEUED'
            Run.objects.create(
                instance=inst,
                client=inst.client,
                pipeline=inst.pipeline,
                status='QUEUED',
                step='DATA_RECOLLECTION',
                last_log='Queued by daily planner'
            )
            queued_count += 1
            
    return f"Planner finished. {queued_count} runs queued for today."

# ----------------------------------------------------------------------------------
# 2. HEARTBEAT DISPATCHER
# Schedule: Run every 1-5 minutes
# ----------------------------------------------------------------------------------
@shared_task(name="heartbeat_dispatcher")
def heartbeat_dispatcher():
    """Checks concurrency limits and time windows to trigger execution of QUEUED runs."""
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
    
    # Pick the next runs that are QUEUED, ordered by updated_at 
    # (to ensure PAUSED runs go to the back when re-queued as QUEUED)
    to_run = Run.objects.filter(
        status='QUEUED'
    ).order_by('updated_at')[:slots_available]

    for run in to_run:
        # Mark as RUNNING immediately to occupy slot in the next dispatcher check
        run.status = 'RUNNING'
        run.save()
        
        # Trigger the actual worker task
        run_pipeline_instance.delay(run.id)

    return f"Dispatched {to_run.count()} runs."

# ----------------------------------------------------------------------------------
# 3. WORKER EXECUTION
# ----------------------------------------------------------------------------------
@shared_task(bind=True, name="run_pipeline_instance")
def run_pipeline_instance(self, run_id):
    """The heavy lifter: Runs the Python script via subprocess."""
    run = Run.objects.get(id=run_id)
    instance = run.instance
    conf = ScraperSettings.get_settings()
    
    # Increment attempt
    run.attempt += 1
    
    # If a run attempt is higher than ScraperSettings max_execution_attempts, set to FAILED
    if run.attempt > conf.max_execution_attempts:
        run.status = 'FAILED'
        run.last_log = f"Exceeded max execution attempts ({conf.max_execution_attempts})"
        run.save()
        return f"Failed: Max attempts reached for run {run.id}"

    # Ensure status is RUNNING before starting (it might be QUEUED if called directly)
    run.status = 'RUNNING'
    run.last_log = f"Attempt {run.attempt} started"
    run.save()
    
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
        
        # Refresh run from DB (script might have updated it via API, e.g. to PAUSED)
        run.refresh_from_db()

        if result.returncode == 0:
            # If the script didn't set it to PAUSED, it's FINISHED
            if run.status != 'PAUSED':
                run.status = 'FINISHED'
                instance.last_run_at = timezone.now()
            # If PAUSED, it will be handled in the 'finally' block to be re-queued
        else:
            run.status = 'FAILED'
            run.last_log = result.stderr
            return f"Failed:{result.stderr}"
            
    except subprocess.TimeoutExpired:
        run.status = 'FAILED'
        run.last_log = "Error: Task timed out after 1 hour."
        return "Failed: Timeout"
    except Exception as e:
        run.status = 'FAILED'
        run.last_log = f"System Error: {str(e)}"
        return f"Failed: {str(e)}"
    
    finally:
        # Final status check: If PAUSED, re-execute with same run entry after ones already queued
        # By setting it back to QUEUED, the heartbeat_dispatcher will pick it up later.
        run.refresh_from_db()
        if run.status == 'PAUSED':
            run.status = 'QUEUED'
            run.last_log = f"Run paused at attempt {run.attempt}. Re-queued."
        
        run.save()
        instance.save()
        
    return f"Finished run {run.id} for {instance.pipeline.name}"