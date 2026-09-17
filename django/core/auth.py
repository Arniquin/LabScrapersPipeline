from django.conf import settings
from ninja.security import APIKeyHeader

class InternalAuth(APIKeyHeader):
    param_name = "X-Internal-Secret"

    def authenticate(self, request, key):
        if key == settings.PIPELINE_API_SECRET:
            return key
        return None