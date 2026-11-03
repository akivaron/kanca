"""Small API client shared by the MCP server and its tests."""
import os
from urllib.parse import quote
import httpx


class KancaClient:
    def __init__(self, base_url=None, api_key=None, transport=None):
        self.base_url = (base_url or os.getenv('KANCA_URL', 'http://127.0.0.1:8765')).rstrip('/')
        self.api_key = api_key if api_key is not None else os.getenv('KANCA_API_KEY', '')
        if not self.api_key:
            raise ValueError('KANCA_API_KEY not configured')
        self.transport = transport

    def request(self, method, path, *, params=None, body=None):
        try:
            with httpx.Client(base_url=self.base_url, headers={'X-API-Key': self.api_key}, timeout=90, transport=self.transport) as client:
                response = client.request(method, path, params=params, json=body)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get('detail', 'Request rejected')
            except ValueError:
                detail = 'Request rejected'
            raise ValueError(f'Kanca rejected the request ({exc.response.status_code}): {detail}') from None
        except (httpx.RequestError, ValueError) as exc:
            if isinstance(exc, httpx.RequestError):
                raise ValueError('Could not connect to the Kanca API') from None
            raise

    def list_sources(self):
        return self.request('GET', '/v1/sources')

    def source_events(self, source_id):
        return self.request('GET', f'/v1/sources/{quote(source_id, safe="")}/events')

    def query_source(self, source_id, question):
        return self.request('POST', f'/v1/sources/{quote(source_id, safe="")}/query', body={'question': question})

    def connections(self):
        return self.request('GET', '/v1/connections')

    def connection_resources(self, connection_id):
        return self.request('GET', f'/v1/connections/{quote(connection_id, safe="")}/resources')

    def create_task(self, instruction):
        return self.request('POST', '/v1/tasks', body={'instruction': instruction})

    def get_task(self, task_id):
        return self.request('GET', f'/v1/tasks/{quote(task_id, safe="")}')

    def tasks(self):
        return self.request('GET', '/v1/tasks')

    def task_runs(self, task_id):
        return self.request('GET', f'/v1/tasks/{quote(task_id, safe="")}/runs')

    def events(self, after=0, limit=100):
        return self.request('GET', '/v1/events', params={'after': after, 'limit': limit})

    def rerun(self, task_id):
        return self.request('POST', f'/v1/tasks/{quote(task_id, safe="")}/rerun')
