"""Opt-in PostgreSQL integration tests: set KANCA_TEST_DATABASE_URL to a disposable DB."""
import os
import uuid
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import pytest

URL = os.getenv('KANCA_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='KANCA_TEST_DATABASE_URL tidak tersedia')


@pytest.fixture
def pg_client(monkeypatch):
    psycopg = pytest.importorskip('psycopg')
    from fastapi.testclient import TestClient
    from app.main import app
    schema = 'test_' + uuid.uuid4().hex
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
    parts = urlsplit(URL)
    params = dict(parse_qsl(parts.query)); params['options'] = f'-csearch_path={schema}'
    test_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
    monkeypatch.setenv('DATABASE_URL', test_url)
    monkeypatch.setenv('KANCA_API_KEY', 'test-key')
    try:
        with TestClient(app, headers={'X-API-Key':'test-key'}) as client:
            yield client
    finally:
        with psycopg.connect(URL, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_postgres_task_worker_and_event_cursor(pg_client):
    from app.service import run_one
    assert pg_client.post('/v1/connections', json={'type':'device_demo'}).status_code == 201
    body = {'instruction':'Periksa', 'explicit_steps':[{'capability':'device.read_temperature','arguments':{}}]}
    first = pg_client.post('/v1/tasks', json=body, headers={'Idempotency-Key':'postgres-test'}).json()
    second = pg_client.post('/v1/tasks', json=body, headers={'Idempotency-Key':'postgres-test'}).json()
    assert first['id'] == second['id']
    assert pg_client.post(f"/v1/tasks/{first['id']}/approve", json={'version':1}).status_code == 200
    assert run_one()
    assert pg_client.get(f"/v1/tasks/{first['id']}").json()['status'] == 'completed'
    events = pg_client.get('/v1/events').json()
    assert len(events) >= 4 and [e['cursor'] for e in events] == sorted(e['cursor'] for e in events)
    assert pg_client.get('/v1/events', params={'after':events[-1]['cursor']}).json() == []


def test_sqlite_import_preserves_events(pg_client, monkeypatch, tmp_path):
    from app.storage import initialize, connect, event
    from app.migrate_sqlite import migrate
    pg_url = os.environ['DATABASE_URL']
    monkeypatch.delenv('DATABASE_URL')
    sqlite_path = tmp_path / 'legacy.db'
    monkeypatch.setenv('KANCA_DB_PATH', str(sqlite_path))
    initialize()
    with connect() as db:
        event(db, 'default', 'task-old', 'task.completed.v1', {'status':'completed'})
    monkeypatch.setenv('DATABASE_URL', pg_url)
    assert migrate(str(sqlite_path))['events'] == 1
    events = pg_client.get('/v1/events').json()
    assert events[0]['cursor'] == 1 and events[0]['data']['status'] == 'completed'
    with pytest.raises(ValueError, match='harus kosong'):
        migrate(str(sqlite_path))
