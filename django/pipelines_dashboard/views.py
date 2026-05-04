import json
from pathlib import Path
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from core.models import Pipeline, Run, Client


# ----------------------------------------------------------------------------------
# PIPELINES VIEWS AND FUNCTIONS
# ----------------------------------------------------------------------------------
def pipelines(request):
    # Fetch data for the initial load
    pipelines = Pipeline.objects.all().order_by('name')
    recent_runs = Run.objects.all().order_by('-created_at')[:10]
    
    return render(request, 'dashboard/pipelines.html', {
        'pipelines': pipelines,
        'recent_runs': recent_runs
    })

def load_pipelines(request):
    if request.method == "POST":
        pipeline_path = Path("./jupyter_data/scraper_pipelines/pipelines")
        
        if not pipeline_path.exists():
            return HttpResponse(f"Error: Directory not found at {pipeline_path}", status=500)

        # 1. Scan and Add new pipelines
        files = [f.name for f in pipeline_path.glob("*.ipynb")]
        for filename in files:
            Pipeline.objects.get_or_create(name=filename.split(".")[0])
            
        # 2. Fetch the UPDATED list from the database
        updated_pipelines = Pipeline.objects.all().order_by('name')
        
        # 3. Render ONLY the table rows and send them back to HTMX
        return render(request, 'dashboard/partials/pipeline_rows.html', {
            'pipelines': updated_pipelines
        })

def update_pipeline(request, pipeline_id):
    if request.method == "POST":
        pipeline = get_object_or_404(Pipeline, id=pipeline_id)
        
        # 1. Define paths using pathlib "/" operator
        # Base: /app/jupyter_data/scraper_pipelines/
        base_path = Path("./jupyter_data/scraper_pipelines")
        pipelines_dir = base_path / 'pipelines'
        scripts_dir = base_path / 'pipelines_scripts'
        
        # Ensure the scripts directory exists
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        notebook_path = pipelines_dir / f"{pipeline.name}.ipynb"
        script_path = scripts_dir / f"{pipeline.name}.py"
        
        # 2. Check if notebook exists
        if not notebook_path.exists():
            return HttpResponse(
                "<span class='text-red-400 text-sm italic'>Notebook not found</span>", 
                status=404
            )

        try:
            # 3. Read the JSON notebook
            with notebook_path.open('r', encoding='utf-8') as f:
                notebook_data = json.load(f)
                
            script_lines = [
                f'"""\nAUTO-GENERATED FROM {pipeline.name}.ipynb\n',
                'Project: LabScrapersPipeline\n"""\n\n'
            ]
            
            # 4. Extract only code cells
            for cell in notebook_data.get('cells', []):
                if cell.get('cell_type') == 'code':
                    code_block = "".join(cell.get('source', []))
                    if code_block.strip():
                        script_lines.append(code_block + "\n\n")
                        
            # 5. Write the resulting .py file
            script_path.write_text("".join(script_lines), encoding='utf-8')
                
            # Success UI feedback for HTMX
            return HttpResponse(f'''
                <button class="inline-flex items-center justify-center gap-x-2 text-base font-bold bg-green-600 px-3 py-2 rounded text-white cursor-default">
                    <span class="material-symbols-outlined text-2xl">check_circle</span>
                    <span>Updated</span>
                </button>
            ''')
            
        except Exception as e:
            return HttpResponse(f"<span class='text-red-400 text-xs'>Error: {str(e)}</span>", status=500)

    return HttpResponse("Method not allowed", status=405)


# ----------------------------------------------------------------------------------
# CLIENTS VIEWS AND FUNCTIONS
# ----------------------------------------------------------------------------------
def clients_list(request):
    """Renders the main client page and table."""
    clients = Client.objects.all().order_by('name')
    return render(request, 'dashboard/clients.html', {'clients': clients})

def client_details(request, client_id):
    """
    Returns the expanded accordion partial showing the client's assigned pipelines.
    Triggered by the 'expand_more' button.
    """
    client = get_object_or_404(Client, id=client_id)
    
    # Get all pipelines that are NOT currently linked to this client
    available_pipelines = Pipeline.objects.exclude(clients=client).order_by('name')
    
    return render(request, 'dashboard/partials/client_expanded.html', {
        'client': client,
        'available_pipelines': available_pipelines
    })


def update_client_pipelines(request, client_id):
    if request.method == "POST":
        client = get_object_or_404(Client, id=client_id)
        pipeline_id = request.POST.get('pipeline_id')
        action = request.POST.get('action') # 'add' or 'remove'
        
        if pipeline_id and action:
            pipeline = get_object_or_404(Pipeline, id=pipeline_id)
            
            if action == 'add':
                client.pipelines.add(pipeline)
            elif action == 'remove':
                client.pipelines.remove(pipeline)
        
        # We return the Toggle partial with expanded=True to refresh everything
        # and keep the accordion open after the update.
        available_pipelines = Pipeline.objects.exclude(clients=client).order_by('name')
        
        return render(request, 'dashboard/partials/client_row_toggle.html', {
            'client': client,
            'expanded': True,
            'available_pipelines': available_pipelines
        })

def client_add_form(request):
    """Returns a table row containing input fields to create a new client."""
    return render(request, 'dashboard/partials/add_client_form.html')

# pipelines_dashboard/views.py

def add_client(request):
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email', '')
        
        if name:
            new_client = Client.objects.create(name=name, email=email)
            # Return the standard row partial so it appears in the list instantly
            return render(request, 'dashboard/partials/client_row_toggle.html', {
                'client': new_client,
                'expanded': False
            })
    return HttpResponse("Invalid Data", status=400)

def delete_client(request, client_id):
    """
    Deletes a client and returns an empty response.
    HTMX will use this empty response to delete the row from the HTML table.
    """
    if request.method in ["POST", "DELETE"]:
        client = get_object_or_404(Client, id=client_id)
        client.delete()
        
        # Returning an empty string tells HTMX to swap the target row with nothing (removing it)
        return HttpResponse("") 
        
    return HttpResponse("Method not allowed", status=405)

# pipelines_dashboard/views.py

def toggle_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    # Check the current state from the request
    is_expanded = request.GET.get('expanded') == 'true'
    
    # We will return a partial that contains BOTH the row and the details
    # If it was expanded, we "collapse" it (expanded=False)
    # If it was collapsed, we "expand" it (expanded=True)
    context = {
        'client': client,
        'expanded': not is_expanded,
    }
    
    if context['expanded']:
        context['available_pipelines'] = Pipeline.objects.exclude(clients=client).order_by('name')
        
    return render(request, 'dashboard/partials/client_row_toggle.html', context)