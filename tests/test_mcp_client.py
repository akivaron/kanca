import httpx
import pytest
from app.mcp_client import KancaClient


def test_mcp_client_uses_api_and_keeps_approval():
    seen = []
    def handler(request):
        seen.append(request)
        assert request.headers['X-API-Key'] == 'test-secret'
        if request.url.path == '/v1/tasks' and request.method == 'POST':
            return httpx.Response(201, json={'id':'task-1','status':'awaiting_approval'})
        if request.url.path == '/v1/events':
            return httpx.Response(200, json=[{'cursor':7,'type':'task.completed.v1'}])
        return httpx.Response(404, json={'detail':'not found'})
    client = KancaClient('http://kanca.local', 'test-secret', transport=httpx.MockTransport(handler))
    assert client.create_task('Periksa suhu')['status'] == 'awaiting_approval'
    assert client.events(after=4, limit=10)[0]['cursor'] == 7
    assert seen[-1].url.params['after'] == '4'
    assert all('/approve' not in request.url.path for request in seen)


def test_mcp_client_handles_errors_without_key_leak():
    def handler(request):
        return httpx.Response(401, json={'detail':'Unauthorized'})
    client = KancaClient('http://kanca.local', 'test-secret', transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError) as exc:
        client.list_sources()
    assert '401' in str(exc.value)
    assert 'test-secret' not in str(exc.value)
