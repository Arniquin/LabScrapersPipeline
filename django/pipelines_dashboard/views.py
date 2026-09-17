import json
from pathlib import Path
from datetime import datetime, time
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from core.models import Pipeline, Run, Client, PipelineInstance, ScraperSettings
from core.tasks import run_pipeline_instance

from django.template.loader import render_to_string

# ----------------------------------------------------------------------------------
# PIPELINES VIEWS
# ----------------------------------------------------------------------------------
def _annotate_pipelines(pipelines):
    """Annotates pipeline objects with has_notebook and has_script flags."""
    base_path = Path("./jupyter_data/scraper_pipelines")
    notebooks_dir = base_path / 'pipelines'
    scripts_dir = base_path / 'pipelines_scripts'
    
    notebook_names = {f.stem for f in notebooks_dir.glob("*.ipynb")} if notebooks_dir.exists() else set()
    script_names = {f.stem for f in scripts_dir.glob("*.py")} if scripts_dir.exists() else set()
    
    for p in pipelines:
        p.has_notebook = p.name in notebook_names
        p.has_script = p.name in script_names
    return pipelines

def pipelines(request):
    pipelines = Pipeline.objects.all().order_by('name')
    pipelines = _annotate_pipelines(pipelines)
    
    recent_runs = Run.objects.all().select_related('client', 'pipeline').order_by('-created_at')[:10]
    
    return render(request, 'dashboard/pipelines.html', {
        'pipelines': pipelines,
        'recent_runs': recent_runs
    })

def load_pipelines(request):
    if request.method == "POST":
        base_path = Path("./jupyter_data/scraper_pipelines")
        pipelines_dir = base_path / 'pipelines'
        scripts_dir = base_path / 'pipelines_scripts'
        
        names = set()
        if pipelines_dir.exists():
            names.update(f.stem for f in pipelines_dir.glob("*.ipynb"))
        if scripts_dir.exists():
            names.update(f.stem for f in scripts_dir.glob("*.py"))
            
        for name in names:
            Pipeline.objects.get_or_create(name=name)
            
        updated_pipelines = Pipeline.objects.all().order_by('name')
        updated_pipelines = _annotate_pipelines(updated_pipelines)
        
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
            _annotate_pipelines([pipeline])
            response = render(request, 'dashboard/partials/pipeline_rows.html', {'pipelines': [pipeline]})
            response['HX-Trigger'] = json.dumps({
                "showToast": {"type": "error", "message": f"Notebook {pipeline.name}.ipynb missing"}
            })
            return response

        try:
            with notebook_path.open('r', encoding='utf-8') as f:
                notebook_data = json.load(f)

            script_lines = [
                f'# AUTO-GENERATED FROM {pipeline.name}.ipynb\n',
                'import asyncio\n\n',
                'async def main():\n'
            ]
            in_actions = False
            for cell in notebook_data.get('cells', []):
                cell_type = cell.get('cell_type')
                source = "".join(cell.get('source', []))

                if cell_type == 'markdown':
                    stripped_source = source.strip()
                    if stripped_source == "#### Actions":
                        in_actions = True
                    elif stripped_source.startswith("#"):
                        in_actions = False

                if cell_type == 'code':
                    code = source
                    if code.strip():
                        if in_actions:
                            indented_code = "\n".join(["        " + line for line in code.splitlines()])
                            code = (
                                "    try:\n"
                                f"{indented_code}\n"
                                "    except Exception as e:\n"
                                "        await scraper.stop()\n"
                                f"        handle_error(PIPELINE_NAME, run, \"DATA_RECOLLECTION\", e)"
                            )
                        else:
                            code = "\n".join(["    " + line for line in code.splitlines()])
                        script_lines.append(code + "\n\n")

            script_lines.append('\nif __name__ == "__main__":\n    asyncio.run(main())\n')
            full_script = "".join(script_lines)
            full_script = full_script.replace("IS_DEVELOPMENT = True", "IS_DEVELOPMENT = False")
            script_path.write_text(full_script, encoding='utf-8')

            _annotate_pipelines([pipeline])
            response = render(request, 'dashboard/partials/pipeline_rows.html', {'pipelines': [pipeline]})
            response['HX-Trigger'] = json.dumps({
                "showToast": {"type": "success", "message": f"Successfully built {pipeline.name}.py"}
            })
            return response
        except Exception as e:
            _annotate_pipelines([pipeline])
            response = render(request, 'dashboard/partials/pipeline_rows.html', {'pipelines': [pipeline]})
            response['HX-Trigger'] = json.dumps({
                "showToast": {"type": "error", "message": str(e)}
            })
            return response

def upload_pipeline_script(request, pipeline_id):
    if request.method == "POST" and request.FILES.get('script_file'):
        pipeline = get_object_or_404(Pipeline, id=pipeline_id)
        script_file = request.FILES['script_file']
        
        if not script_file.name.endswith('.py'):
            _annotate_pipelines([pipeline])
            response = render(request, 'dashboard/partials/pipeline_rows.html', {'pipelines': [pipeline]})
            response['HX-Trigger'] = json.dumps({
                "showToast": {"type": "error", "message": "Only .py files allowed"}
            })
            return response
            
        scripts_dir = Path("./jupyter_data/scraper_pipelines/pipelines_scripts")
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / f"{pipeline.name}.py"
        
        with open(script_path, 'wb+') as destination:
            for chunk in script_file.chunks():
                destination.write(chunk)
        
        _annotate_pipelines([pipeline])
        response = render(request, 'dashboard/partials/pipeline_rows.html', {'pipelines': [pipeline]})
        response['HX-Trigger'] = json.dumps({
            "showToast": {"type": "success", "message": f"Uploaded {script_file.name}"}
        })
        return response
    return HttpResponse("Invalid request", status=400)

def upload_new_pipeline(request):
    if request.method == "POST" and request.FILES.get('script_file'):
        script_file = request.FILES['script_file']
        if not script_file.name.endswith('.py'):
            updated_pipelines = Pipeline.objects.all().order_by('name')
            _annotate_pipelines(updated_pipelines)
            response = render(request, 'dashboard/partials/pipeline_rows.html', {'pipelines': updated_pipelines})
            response['HX-Trigger'] = json.dumps({
                "showToast": {"type": "error", "message": "Only .py files allowed"}
            })
            return response
            
        pipeline_name = Path(script_file.name).stem
        pipeline, _ = Pipeline.objects.get_or_create(name=pipeline_name)
        
        scripts_dir = Path("./jupyter_data/scraper_pipelines/pipelines_scripts")
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / f"{pipeline_name}.py"
        
        with open(script_path, 'wb+') as destination:
            for chunk in script_file.chunks():
                destination.write(chunk)
        
        updated_pipelines = Pipeline.objects.all().order_by('name')
        updated_pipelines = _annotate_pipelines(updated_pipelines)
        
        response = render(request, 'dashboard/partials/pipeline_rows.html', {'pipelines': updated_pipelines})
        response['HX-Trigger'] = json.dumps({
            "showToast": {"type": "success", "message": f"New pipeline {pipeline_name} created"}
        })
        return response
    return HttpResponse("Invalid request", status=400)

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
                    alias=alias
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
    instance = get_object_or_404(PipelineInstance, id=instance_id)
    params_str = json.dumps(instance.pipeline_params, indent=4)
    return render(request, 'dashboard/partials/instance_params_form.html', {
        'instance': instance,
        'params_str': params_str
    })

def update_instance_params(request, instance_id):
    instance = get_object_or_404(PipelineInstance, id=instance_id)
    if request.method == "POST":
        new_params_raw = request.POST.get('pipeline_params')
        try:
            instance.pipeline_params = json.loads(new_params_raw)
            instance.save()
        except json.JSONDecodeError:
            return HttpResponse("Invalid JSON", status=400)
            
    return render(request, 'dashboard/partials/instance_params_display.html', {'instance': instance})

# ----------------------------------------------------------------------------------
# SCHEDULER VIEWS
# ----------------------------------------------------------------------------------
def scheduler_view(request):
    client_q = request.GET.get('client_q', '')
    pipeline_q = request.GET.get('pipeline_q', '')
    clients = Client.objects.prefetch_related('pipeline_instances__pipeline').all()
    if client_q:
        clients = clients.filter(name__icontains=client_q)
    if pipeline_q:
        clients = clients.filter(pipeline_instances__pipeline__name__icontains=pipeline_q).distinct()
    settings = ScraperSettings.get_settings()
    pending_runs_count = Run.objects.filter(status='QUEUED').count()
    return render(request, 'dashboard/scheduler.html', {
        'clients': clients,
        'settings': settings,
        'pending_runs_count': pending_runs_count,
        'client_q': client_q,
        'pipeline_q': pipeline_q
    })

def update_scheduler_settings(request):
    settings = ScraperSettings.get_settings()
    if 'limit' in request.POST:
        settings.max_concurrent_instances = request.POST.get('limit')
    if 'start' in request.POST:
        settings.window_start_hour = request.POST.get('start')
    if 'end' in request.POST:
        settings.window_end_hour = request.POST.get('end')
    if 'attempts' in request.POST:
        settings.max_execution_attempts = request.POST.get('attempts')
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
    if request.method == "POST":
        instance = get_object_or_404(PipelineInstance, id=instance_id)
        run = Run.objects.create(
            instance=instance,
            client=instance.client,
            pipeline=instance.pipeline,
            status='RUNNING',
            step='DATA_RECOLLECTION',
            last_log='Manual trigger started'
        )
        run_pipeline_instance.delay(run.id)
        return HttpResponse('<span class="text-[10px] bg-green-500/20 text-green-400 px-2 py-1 rounded border border-green-500/30 animate-bounce">Queued</span>')

# ----------------------------------------------------------------------------------
# RUNS VIEWS
# ----------------------------------------------------------------------------------
def runs_view(request):
    today_str = timezone.now().date().isoformat()
    start_date_str = request.GET.get('start_date', today_str)
    end_date_str = request.GET.get('end_date', today_str)
    client_q = request.GET.get('client_q', '')
    pipeline_q = request.GET.get('pipeline_q', '')
    alias_q = request.GET.get('alias_q', '')
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max))
    runs = Run.objects.select_related('client', 'pipeline', 'instance').filter(
        created_at__range=(start_dt, end_dt)
    ).order_by('-created_at')
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
