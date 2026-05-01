import os
import requests
from urllib.parse import urljoin

class RunManager:
    def __init__(self, client_name: str, pipeline_name: str):
        self._client_name = client_name
        self._pipeline_name = pipeline_name
        self._api_token = os.getenv('PIPELINE_API_SECRET')
        self._api_base_url = os.getenv('DJANGO_API_URL')
        
        self.session = requests.Session()
        self.session.headers.update({
            'X-Internal-Secret': self._api_token,
            'Content-Type': 'application/json' 
        })
        
        self._status = "RUNNING"
        self._step = "DATA_RECOLLECTION"
        self._last_log = "Initializing..."
        
        # Automatic start
        self._run_id = self._start_run()

    def _get_url(self, endpoint: str):
        # Ensure base URL ends with slash for urljoin
        base = self._api_base_url if self._api_base_url.endswith('/') else f"{self._api_base_url}/"
        return urljoin(base, endpoint.lstrip('/'))

    def _start_run(self) -> str:
        url = self._get_url("runs/start")
        body = {
            "client_name": self._client_name,
            "pipeline_name": self._pipeline_name,
            "initial_step": self._step
        }
        response = self.session.post(url, json=body)
        response.raise_for_status()
        return response.json()['run_id']

    def update_run(self, status, step, last_log):
        url = self._get_url(f"runs/{self._run_id}/update")
        self._status = status
        self._step = step
        self._last_log = last_log
        body = {
            "status": status,
            "step": step,
            "last_log": last_log
        }
        response = self.session.patch(url, json=body)
        response.raise_for_status()

    def store_raw_data(self, data_dict):
        url = self._get_url(f"runs/{self._run_id}/raw")
        response = self.session.post(url, json={"payload": data_dict})
        response.raise_for_status()

    def store_cleaned_data(self, data_dict):
        url = self._get_url(f"runs/{self._run_id}/cleaned")
        response = self.session.post(url, json={"payload": data_dict})
        response.raise_for_status()

    def set_run_fail(self, last_log):
        self._status = 'FAILED'
        self._last_log = last_log
        self.update_run(self._status, self._step, self._last_log)

    def set_run_end(self, last_log):
        self._status = 'FINISHED'
        self._last_log = last_log
        self.update_run(self._status, self._step, self._last_log)

    @property
    def step(self):
        return self._step

    @step.setter
    def step(self, new_step):
        self._status = 'RUNNING'
        # Fixed the variable names here
        self._last_log = f"Pipeline {self._client_name}-{self._pipeline_name}: Started step {new_step}"
        self.update_run(self._status, new_step, self._last_log)
        self._step = new_step