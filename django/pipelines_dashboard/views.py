import json
from pathlib import Path
from datetime import datetime, time
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from core.models import Pipeline, Run, Client, PipelineInstance, ScraperSettings
from core.tasks import run_pipeline_instance

# ----------------------------------------------------------------------------------
# PIPELINES VIEWS
# ----------------------------------------------------------------------------------
def pipelines(request):
    pipelines = Pipeline.objects.all().order_by('name')
    # Updated to reflect your new Run model structure
    recent_runs = Run.objects.all().select_related('client', 'pipeline').order_by('-created_at')[:10]
    
    return render(request, 'dashboard/pipelines.html', {
        'pipelines': pipelines,
        'recent_runs': recent_runs
    })

def load_pipelines(request):
    if request.method == "POST":
        pipeline_path = Path("./jupyter_data/scraper_pipelines/pipelines")
        if not pipeline_path.exists():
            return HttpResponse(f"Error: Directory not found", status=500)

        files = [f.name for f in pipeline_path.glob("*.ipynb")]
        for filename in files:
            Pipeline.objects.get_or_create(name=filename.split(".")[0])
            
        updated_pipelines = Pipeline.objects.all().order_by('name')
        return render(request, 'dashboard/partials/pipeline_rows.html', {
            'pipelines': updated_pipelines
        })

def update_pipeline(request, pipeline_id):
    if request.method == "POST":
        pipeline = get_object_or_404(Pipeline, id=pipeline_id)
        base_path = Path("./jupyter_data/scraper_pipelines")
        pipelines_dir = base_path / 'pipelines'
        scripts_dir = base_path / 'pipelines_scripts'
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        notebook_path = pipelines_dir / f"{pipeline.name}.ipynb"
        script_path = scripts_dir / f"{pipeline.name}.py"
        
        if not notebook_path.exists():
            return HttpResponse("<span class='text-red-400'>Notebook missing</span>", status=404)

        try:
            with notebook_path.open('r', encoding='utf-8') as f:
                notebook_data = json.load(f)
            
            script_lines = [f'# AUTO-GENERATED FROM {pipeline.name}.ipynb\n\n']
            for cell in notebook_data.get('cells', []):
                if cell.get('cell_type') == 'code':
                    code = "".join(cell.get('source', []))
                    if code.strip():
                        script_lines.append(code + "\n\n")
            
            script_path.write_text("".join(script_lines), encoding='utf-8')
            return HttpResponse('<button class="bg-green-600 px-3 py-2 rounded text-white">Updated</button>')
        except Exception as e:
            return HttpResponse(f"Error: {str(e)}", status=500)

# ----------------------------------------------------------------------------------
# CLIENTS VIEWS
# ----------------------------------------------------------------------------------
def clients_list(request):
    clients = Client.objects.all().order_by('name')
    return render(request, 'dashboard/clients.html', {'clients': clients})

def toggle_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    is_expanded = request.GET.get('expanded') == 'true'
    
    context = {'client': client, 'expanded': not is_expanded}
    if context['expanded']:
        # Changed from .exclude() to .all() because instances allow duplicates
        context['available_pipelines'] = Pipeline.objects.all().order_by('name')
        
    return render(request, 'dashboard/partials/client_row_toggle.html', context)

def update_client_pipelines(request, client_id):
    if request.method == "POST":
        client = get_object_or_404(Client, id=client_id)
        action = request.POST.get('action') 
        
        if action == 'add':
            p_id = request.POST.get('pipeline_id')
            alias = request.POST.get('alias')
            if p_id:
                pipeline = get_object_or_404(Pipeline, id=p_id)
                PipelineInstance.objects.create(
                    client=client, 
                    pipeline=pipeline, 
                    alias=alias # Save the alias here
                )
        elif action == 'remove':
            inst_id = request.POST.get('instance_id')
            if inst_id:
                get_object_or_404(PipelineInstance, id=inst_id).delete()
        
        return render(request, 'dashboard/partials/client_row_toggle.html', {
            'client': client,
            'expanded': True,
            'available_pipelines': Pipeline.objects.all().order_by('name')
        })

def client_add_form(request):
    """Returns the partial row containing the input fields to create a new client."""
    return render(request, 'dashboard/partials/add_client_form.html')

def add_client(request):
    if request.method == "POST":
        name, email = request.POST.get('name'), request.POST.get('email', '')
        if name:
            new_client = Client.objects.create(name=name, email=email)
            return render(request, 'dashboard/partials/client_row_toggle.html', {'client': new_client, 'expanded': False})
    return HttpResponse("Invalid Data", status=400)

def delete_client(request, client_id):
    if request.method in ["POST", "DELETE"]:
        get_object_or_404(Client, id=client_id).delete()
        return HttpResponse("") 
    return HttpResponse(status=405)

def edit_instance_params(request, instance_id):
    """Returns a textarea form for the JSON params."""
    instance = get_object_or_404(PipelineInstance, id=instance_id)
    # Convert dict to pretty-printed string for editing
    params_str = json.dumps(instance.pipeline_params, indent=4)
    return render(request, 'dashboard/partials/instance_params_form.html', {
        'instance': instance,
        'params_str': params_str
    })

def update_instance_params(request, instance_id):
    """Saves the JSON string back to the database."""
    instance = get_object_or_404(PipelineInstance, id=instance_id)
    if request.method == "POST":
        new_params_raw = request.POST.get('pipeline_params')
        try:
            # Validate and save
            instance.pipeline_params = json.loads(new_params_raw)
            instance.save()
        except json.JSONDecodeError:
            return HttpResponse("Invalid JSON", status=400)
            
    return render(request, 'dashboard/partials/instance_params_display.html', {'instance': instance})

# ----------------------------------------------------------------------------------
# SCHEDULER VIEWS
# ----------------------------------------------------------------------------------
def scheduler_view(request):
    # Get filter values from the GET request
    client_q = request.GET.get('client_q', '')
    pipeline_q = request.GET.get('pipeline_q', '')

    # Start with all clients and prefetch instances
    clients = Client.objects.prefetch_related('pipeline_instances__pipeline').all()

    # Apply Client Filter
    if client_q:
        clients = clients.filter(name__icontains=client_q)

    # Apply Pipeline Filter
    if pipeline_q:
        # We filter clients that HAVE instances matching the pipeline name
        clients = clients.filter(pipeline_instances__pipeline__name__icontains=pipeline_q).distinct()

    settings = ScraperSettings.get_settings()
    
    return render(request, 'dashboard/scheduler.html', {
        'clients': clients,
        'settings': settings,
        'client_q': client_q,
        'pipeline_q': pipeline_q
    })

def update_scheduler_settings(request):
    """Updates global concurrency or time window."""
    settings = ScraperSettings.get_settings()
    if 'limit' in request.POST:
        settings.max_concurrent_instances = request.POST.get('limit')
    if 'start' in request.POST:
        settings.window_start_hour = request.POST.get('start')
    if 'end' in request.POST:
        settings.window_end_hour = request.POST.get('end')
    settings.save()
    return HttpResponse(status=204)

def update_instance_frequency(request, instance_id):
    instance = get_object_or_404(PipelineInstance, id=instance_id)
    instance.frequency = request.POST.get('frequency')
    instance.save()
    return HttpResponse(status=204)

def toggle_instance_active(request, instance_id):
    instance = get_object_or_404(PipelineInstance, id=instance_id)
    instance.is_active = not instance.is_active
    instance.save()
    return HttpResponse(status=204)

def run_instance_manual(request, instance_id):
    """Triggers the Celery worker immediately, bypassing the dispatcher window."""
    if request.method == "POST":
        # We don't mark it as 'is_queued' because we are sending it directly to Redis
        run_pipeline_instance.delay(instance_id)
        
        # Return a little 'Success' badge that HTMX will show on the button
        return HttpResponse('''
            <span class="text-[10px] bg-green-500/20 text-green-400 px-2 py-1 rounded border border-green-500/30 animate-bounce">
                Queued
            </span>
        ''')

# ----------------------------------------------------------------------------------
# RUNS VIEWS
# ----------------------------------------------------------------------------------

def runs_view(request):
    # 1. Get Date Filters (Default to Today)
    today_str = timezone.now().date().isoformat()
    start_date_str = request.GET.get('start_date', today_str)
    end_date_str = request.GET.get('end_date', today_str)
    
    # 2. Get Search Filters
    client_q = request.GET.get('client_q', '')
    pipeline_q = request.GET.get('pipeline_q', '')
    alias_q = request.GET.get('alias_q', '')

    # 3. Convert strings to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    # Create time-aware range (start of start_date to end of end_date)
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max))

    # 4. Query with select_related to keep the ProBook Node fast
    runs = Run.objects.select_related('client', 'pipeline', 'instance').filter(
        created_at__range=(start_dt, end_dt)
    ).order_by('-created_at')

    # 5. Apply Text Filters
    if client_q:
        runs = runs.filter(client__name__icontains=client_q)
    if pipeline_q:
        runs = runs.filter(pipeline__name__icontains=pipeline_q)
    if alias_q:
        runs = runs.filter(instance__alias__icontains=alias_q)

    return render(request, 'dashboard/runs.html', {
        'runs': runs,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'client_q': client_q,
        'pipeline_q': pipeline_q,
        'alias_q': alias_q,
    })