# utils/run_manager.py
import os
import requests
from typing import Any, Dict, Optional
from urllib.parse import urljoin

class RunManager:
    VALID_STATUSES = ['RUNNING', 'FINISHED', 'FAILED', 'PAUSED']
    VALID_STEPS = [
        'DATA_RECOLLECTION', 
        'STORING_RAW_DATA', 
        'CLEANING_RAW_DATA', 
        'STORING_CLEANED_DATA'
    ]

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._api_token = os.getenv('PIPELINE_API_SECRET')
        self._api_base_url = os.getenv('DJANGO_API_URL', 'http://django_app:8000')
        
        self.session = requests.Session()
        self.session.headers.update({
            'X-Internal-Secret': self._api_token,
            'Content-Type': 'application/json' 
        })

    @classmethod
    def start_run(cls, instance_id: str, initial_step: str = "DATA_RECOLLECTION") -> Optional['RunManager']:
        """
        Initiates a run linked to a specific PipelineInstance.
        Returns a RunManager instance configured with the new run_id.
        """
        api_base_url = os.getenv('DJANGO_API_URL', 'http://django_app:8000')
        api_token = os.getenv('PIPELINE_API_SECRET')
        
        url = urljoin(api_base_url, "/pipeline_api/runs/start")
        payload = {
            "instance_id": instance_id,
            "initial_step": initial_step
        }
        headers = {'X-Internal-Secret': api_token}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            run_id = response.json().get("run_id")
            return cls(run_id=run_id)
        except Exception as e:
            print(f"RunManager failed to start: {e}")
            return None

    def update(self, status: str = None, step: str = None, last_log: str = None):
        payload = {}
        if status in self.VALID_STATUSES: payload['status'] = status
        if step in self.VALID_STEPS: payload['step'] = step
        if last_log: payload['last_log'] = last_log
        
        url = urljoin(self._api_base_url, f"/pipeline_api/runs/{self.run_id}/update")
        try:
            self.session.patch(url, json=payload, timeout=10).raise_for_status()
            return True
        except Exception as e:
            print(f"Update failed: {e}")
            return False
    def set_run_fail(self, log: str):
        return self.update(status='FAILED', last_log=log)

    def log(self, message: str):
        """Standard logging to the dashboard's last_log field."""
        return self.update(last_log=message)

    def save_raw_data(self, payload: Dict[str, Any]):
        url = urljoin(self._api_base_url, f"/pipeline_api/runs/{self.run_id}/raw")
        return self.session.post(url, json={'payload': payload}, timeout=10).json()

    def save_cleaned_data(self, payload: Dict[str, Any]):
        url = urljoin(self._api_base_url, f"/pipeline_api/runs/{self.run_id}/cleaned")
        return self.session.post(url, json={'payload': payload}, timeout=10).json()