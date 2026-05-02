from django.shortcuts import render
from core.models import Run # Adjust this if your model is named differently

def pipeline_dashboard(request):
    # For now, just grab the 10 most recent runs
    recent_runs = Run.objects.all().order_by('-created_at')[:10]
    
    context = {
        'recent_runs': recent_runs,
        'page_title': "Pipeline Control Room"
    }
    return render(request, 'dashboard/index.html', context)