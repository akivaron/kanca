import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.service import run_one


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("KANCA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("KANCA_API_KEY", "test-key")
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c


def connect(client, kind):
    response = client.post("/v1/connections", json={"type": kind})
    assert response.status_code == 201
    return response.json()["id"]


def create(client, capability, args=None, headers=None):
    return client.post("/v1/tasks", headers=headers or {}, json={"instruction": "Tolong jalankan", "explicit_steps": [{"capability": capability, "arguments": args or {}}]})


@pytest.mark.parametrize("kind,capability", [("business_demo", "business.list_orders"), ("device_demo", "device.read_temperature")])
def test_approval_worker_and_event(client, kind, capability):
    connect(client, kind)
    task = create(client, capability).json()
    assert task["status"] == "awaiting_approval"
    assert run_one() is False
    assert client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 2}).status_code == 409
    assert client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 1}).status_code == 200
    assert run_one() is True
    result = client.get(f"/v1/tasks/{task['id']}").json()
    assert result["status"] == "completed"
    assert result["result"]["steps"][0]["capability"] == capability
    events = client.get(f"/v1/tasks/{task['id']}/events").json()
    assert [e["type"] for e in events] == ["task.created.v1", "task.approval_requested.v1", "task.approved.v1", "task.started.v1", "task.completed.v1"]
    assert len({e["id"] for e in events}) == len(events)


def test_revocation_blocks_scheduled_action(client):
    cid = connect(client, "device_demo")
    task = create(client, "device.turn_on_light").json()
    client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 1})
    client.delete(f"/v1/connections/{cid}")
    assert run_one()
    assert client.get(f"/v1/tasks/{task['id']}").json()["status"] == "failed"
    assert not any(e["type"] == "task.action_taken.v1" for e in client.get("/v1/events").json())


def test_validation_idempotency_and_cancel(client):
    connect(client, "business_demo")
    assert create(client, "business.remind", {"message": 123}).status_code == 422
    assert create(client, "missing.tool").status_code == 422
    first = create(client, "business.list_orders", headers={"Idempotency-Key": "one"}).json()
    again = create(client, "business.list_orders", headers={"Idempotency-Key": "one"}).json()
    assert first["id"] == again["id"]
    assert create(client, "business.remind", {"message": "Hai"}, {"Idempotency-Key": "one"}).status_code == 409
    assert client.post(f"/v1/tasks/{first['id']}/cancel").json()["status"] == "cancelled"
    assert not run_one()


def test_missing_api_key_and_demo_mode(client):
    assert client.get("/v1/connections", headers={"X-API-Key": "wrong"}).status_code == 401
    response = client.post("/v1/tasks", json={"instruction": "Apa yang terjadi?"})
    assert response.status_code == 503


def test_api_docs_are_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    response = client.get("/v1/session")
    assert response.status_code == 200


def test_local_ui_session(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("KANCA_DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.setenv("KANCA_API_KEY", "server-secret")
    with TestClient(app) as ui:
        assert ui.get("/v1/connections").status_code == 401
        page = ui.get("/v1/session")
        assert "server-secret" not in page.text
        assert "httponly" in page.headers["set-cookie"].lower()
        assert ui.get("/v1/connections").status_code == 200
        assert ui.post("/v1/connections", json={"type": "device_demo"}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert ui.post("/v1/connections", json={"type": "device_demo"}, headers={"Origin": "http://testserver"}).status_code == 201


def test_baseten_planner_request_and_approval(client, monkeypatch):
    import httpx
    from app import planner
    connect(client, "device_demo")
    monkeypatch.setenv("BASETEN_API_KEY", "test-baseten-key")
    captured = {}

    def mock_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"summary":"Periksa suhu","steps":[{"capability":"device.read_temperature","arguments":{}}]}'}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(planner.httpx, "post", mock_post)
    response = client.post("/v1/tasks", json={"instruction": "Tolong cek suhu"})
    assert response.status_code == 201
    assert response.json()["plan"]["source"] == "baseten"
    assert captured["url"] == "https://inference.baseten.co/v1/chat/completions"
    assert captured["json"]["model"] == "meta-models/muse-spark-open-1026"
    assert captured["headers"]["Authorization"] == "Bearer test-baseten-key"
    assert response.json()["status"] == "awaiting_approval"


def test_repeated_monitoring_and_conditional_action_once(client):
    from app.storage import connect as db_connect
    connect(client, "device_demo")
    body = {"instruction": "Pantau suhu", "schedule": {"interval_seconds": 1, "max_runs": 2}, "explicit_steps": [
        {"capability": "device.read_temperature", "arguments": {}},
        {"capability": "device.turn_on_light", "arguments": {}, "condition": {"step": 0, "field": "temperature_c", "operator": "gt", "value": 28}},
    ]}
    task = client.post("/v1/tasks", json=body).json()
    client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 1})
    assert run_one()
    assert client.get(f"/v1/tasks/{task['id']}").json()["status"] == "scheduled"
    with db_connect() as db:
        db.execute("UPDATE schedules SET next_run='2000-01-01T00:00:00+00:00' WHERE task_id=?", (task["id"],))
    assert run_one()
    runs = client.get(f"/v1/tasks/{task['id']}/runs").json()
    assert len(runs) == 2
    assert runs[1]["results"][1]["status"] == "already_executed"
    assert client.get(f"/v1/tasks/{task['id']}").json()["status"] == "completed"
    assert sum(e["type"] == "task.action_taken.v1" for e in client.get("/v1/events").json()) == 1


def test_webhook_delivery_and_retry(client, monkeypatch):
    from app import webhooks
    from app.storage import connect as db_connect
    import hashlib, hmac
    assert client.post("/v1/webhook-subscriptions", json={"url": "http://localhost"}).status_code == 422
    sub = client.post("/v1/webhook-subscriptions", json={"url": "https://example.com/webhook"}).json()
    connect(client, "device_demo")
    task = create(client, "device.read_temperature").json()
    captured = []
    def fake_post(url, payload, headers):
        captured.append((payload, headers))
        return 500 if len(captured) == 1 else 200
    monkeypatch.setattr(webhooks, "post_pinned", fake_post)
    assert webhooks.deliver_one()
    with db_connect() as db:
        db.execute("UPDATE deliveries SET next_attempt='2000-01-01T00:00:00+00:00' WHERE status='pending'")
    assert webhooks.deliver_one()
    payload, headers = captured[-1]
    expected = hmac.new(sub["secret"].encode(), headers["X-Kanca-Timestamp"].encode() + b"." + payload, hashlib.sha256).hexdigest()
    assert headers["X-Kanca-Signature"] == "sha256=" + expected
    deliveries = client.get("/v1/webhook-deliveries").json()
    assert any(d["status"] == "delivered" and d["attempts"] == 2 for d in deliveries)
    assert "secret" not in client.get("/v1/webhook-subscriptions").json()[0]
    assert client.delete(f"/v1/webhook-subscriptions/{sub['id']}").json()["status"] == "disabled"


def test_business_exception_triggers_simulated_reminder(client):
    connect(client, "business_demo")
    body = {"instruction": "Periksa pesanan dan ingatkan jika belum dikemas", "explicit_steps": [
        {"capability": "business.check_orders", "arguments": {}},
        {"capability": "business.remind", "arguments": {"message": "Mohon periksa pesanan yang belum dikemas."}, "condition": {"step": 0, "field": "unpacked_count", "operator": "gt", "value": 0}},
    ]}
    task = client.post("/v1/tasks", json=body).json()
    assert client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 1}).status_code == 200
    assert run_one()
    result = client.get(f"/v1/tasks/{task['id']}").json()["result"]
    assert result["steps"][0]["result"]["mismatch_count"] == 1
    assert result["steps"][1]["result"]["source"] == "synthetic"
    assert result["steps"][0]["result"]["unverified"]


def test_conversation_history_context_and_topic_isolation(client, monkeypatch):
    from app import main
    calls = []
    def fake_planner(instruction, capabilities, history=None):
        calls.append((instruction, history))
        if len(calls) == 1:
            return {"clarification": "Suhu di mana?", "steps": []}
        return {"summary": "Periksa suhu", "steps": [{"capability": "device.read_temperature", "arguments": {}}]}
    monkeypatch.setattr(main, "propose", fake_planner)
    connect(client, "device_demo")
    first = client.post("/v1/conversations", json={}).json()["id"]
    other = client.post("/v1/conversations", json={"title": "Topik lain"}).json()["id"]
    assert client.post(f"/v1/conversations/{first}/messages", json={"content": "Cek suhu"}).status_code == 201
    assert client.post(f"/v1/conversations/{first}/messages", json={"content": "Ruang tamu"}).status_code == 201
    assert calls[1][1] == [{"role": "user", "content": "Cek suhu"}, {"role": "assistant", "content": "Suhu di mana?"}]
    messages = client.get(f"/v1/conversations/{first}/messages").json()
    assert len(messages) == 4
    task = messages[-1]["task"]
    assert task["status"] == "scheduled"
    assert client.get(f"/v1/conversations/{other}/messages").json() == []
    assert any(chat["title"] == "Cek suhu" for chat in client.get("/v1/conversations").json())
    assert run_one()
    assert client.get(f"/v1/conversations/{first}/messages").json()[-1]["task"]["status"] == "completed"


def test_general_chat_response_without_task(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "propose", lambda instruction, capabilities, history=None: {"answer": "Halo! Aku Kanca. Ada yang bisa kubantu?", "steps": []})
    cid = client.post("/v1/conversations", json={}).json()["id"]
    response = client.post(f"/v1/conversations/{cid}/messages", json={"content": "Halo, siapa kamu?"})
    assert response.status_code == 201
    assert response.json()["content"] == "Halo! Aku Kanca. Ada yang bisa kubantu?"
    assert response.json()["task_id"] is None
    assert len(client.get(f"/v1/conversations/{cid}/messages").json()) == 2


def test_chat_read_only_runs_automatically_but_actions_require_approval(client, monkeypatch):
    from app import main
    connect(client, 'device_demo')
    cid = client.post('/v1/conversations', json={}).json()['id']
    monkeypatch.setattr(main, 'propose', lambda *args: {'answer':'Setujui dulu', 'steps':[{'capability':'device.read_temperature','arguments':{}}]})
    reply = client.post(f'/v1/conversations/{cid}/messages', json={'content':'Cek suhu'}).json()
    task_id = reply['task_id']
    assert 'akan mengerjakannya' in reply['content']
    assert client.get(f'/v1/tasks/{task_id}').json()['status'] == 'scheduled'
    assert any(e['type']=='task.approved.v1' and e['data'].get('mode')=='automatic_safe' for e in client.get(f'/v1/tasks/{task_id}/events').json())
    assert run_one()
    monkeypatch.setattr(main, 'propose', lambda *args: {'answer':'Sudah saya nyalakan', 'steps':[{'capability':'device.read_temperature','arguments':{}},{'capability':'device.turn_on_light','arguments':{}}]})
    reply = client.post(f'/v1/conversations/{cid}/messages', json={'content':'Nyalakan lampu'}).json()
    assert 'setujui' in reply['content']
    assert client.get(f"/v1/tasks/{reply['task_id']}").json()['status'] == 'awaiting_approval'
    assert not run_one()


def test_chat_simulated_reminder_is_safe_and_runs_once(client, monkeypatch):
    from app import main
    connect(client, 'business_demo')
    cid = client.post('/v1/conversations', json={}).json()['id']
    monkeypatch.setattr(main, 'propose', lambda *args: {'steps':[{'capability':'business.remind','arguments':{'message':'Tolong periksa'}}]})
    reply = client.post(f'/v1/conversations/{cid}/messages', json={'content':'Ingatkan admin simulasi'}).json()
    tid = reply['task_id']
    assert client.get(f'/v1/tasks/{tid}').json()['status'] == 'scheduled'
    assert run_one()
    assert any(e['type'] == 'task.action_taken.v1' for e in client.get(f'/v1/tasks/{tid}/events').json())


def test_chat_model_error_is_user_friendly(client, monkeypatch):
    from app import main
    from app.planner import PlanningError
    def fail(*args, **kwargs):
        raise PlanningError("provider technical detail")
    monkeypatch.setattr(main, "propose", fail)
    cid = client.post("/v1/conversations", json={}).json()["id"]
    response = client.post(f"/v1/conversations/{cid}/messages", json={"content": "Halo"})
    assert "provider" not in response.json()["content"]
    assert response.json()["task_id"] is None


def test_task_schedule_changes_require_new_approval_and_archive_stops(client):
    connect(client, "device_demo")
    task = create(client, "device.read_temperature").json()
    assert client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 1}).status_code == 200
    response = client.patch(f"/v1/tasks/{task['id']}/schedule", json={"version": 1, "schedule": {"interval_seconds": 30, "max_runs": 3}})
    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"
    assert response.json()["version"] == 2
    assert not run_one()
    assert client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 1}).status_code == 409
    assert client.post(f"/v1/tasks/{task['id']}/approve", json={"version": 2}).status_code == 200
    archived = client.delete(f"/v1/tasks/{task['id']}").json()
    assert archived == {"status": "cancelled", "archived": True}
    assert not run_one()
    assert not any(t["id"] == task["id"] for t in client.get("/v1/tasks").json())
    assert any(e["type"] == "task.archived.v1" for e in client.get(f"/v1/tasks/{task['id']}/events").json())


def test_external_source_lifecycle_and_ingestion(client):
    source = client.post('/v1/sources', json={'name':'Sensor A','kind':'iot'}).json()
    sid, token = source['id'], source['token']
    assert 'token' not in client.get('/v1/sources').json()[0]
    assert client.post(f'/v1/ingest/{sid}', json={'type':'temperature','data':{'value':29}}).status_code == 401
    headers = {'Authorization': f'Bearer {token}'}
    received = client.post(f'/v1/ingest/{sid}', json={'type':'temperature','data':{'value':29}}, headers=headers)
    assert received.status_code == 202
    assert client.get(f'/v1/sources/{sid}/events').json()[0]['payload'] == {'value':29}
    assert any(e['type'] == 'source.event.v1' for e in client.get('/v1/events').json())
    assert client.put(f'/v1/sources/{sid}', json={'name':'Sensor B','kind':'camera','status':'disabled'}).status_code == 200
    assert client.post(f'/v1/ingest/{sid}', json={'type':'temperature','data':{}}, headers=headers).status_code == 401
    assert client.delete(f'/v1/sources/{sid}').status_code == 200
    assert client.get('/v1/sources').json() == []
    assert client.put(f'/v1/sources/{sid}', json={'name':'Again','kind':'iot','status':'active'}).status_code == 404


def test_chat_draft_restore_and_delete_preserve_tasks(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'propose', lambda *args: {'answer':'Siap', 'steps':[{'capability':'device.read_temperature','arguments':{}}]})
    connect(client, 'device_demo')
    cid = client.post('/v1/conversations', json={}).json()['id']
    task = client.post(f'/v1/conversations/{cid}/messages', json={'content':'Cek suhu'}).json()['task_id']
    assert client.patch(f'/v1/conversations/{cid}', json={'status':'draft'}).json()['status'] == 'draft'
    assert client.get('/v1/conversations').json()[0]['status'] == 'draft'
    assert len(client.get(f'/v1/conversations/{cid}/messages').json()) == 2
    assert client.patch(f'/v1/conversations/{cid}', json={'status':'active'}).json()['status'] == 'active'
    assert client.delete(f'/v1/conversations/{cid}').status_code == 200
    assert client.get('/v1/conversations').json() == []
    assert client.get(f'/v1/conversations/{cid}/messages').status_code == 404
    assert client.get(f'/v1/tasks/{task}').json()['status'] == 'scheduled'


def test_invalid_plan_is_retried_with_feedback(client, monkeypatch):
    from app import main
    calls = []
    def fake_planner(instruction, capabilities, history=None, feedback=None):
        calls.append(feedback)
        field = 'temperature' if feedback is None else 'temperature_c'
        return {'answer':'Aku siapkan rencananya.', 'schedule':{'interval_seconds':30,'max_runs':3}, 'steps':[
            {'capability':'device.read_temperature','arguments':{}},
            {'capability':'device.turn_on_light','arguments':{},'condition':{'step':0,'field':field,'operator':'gt','value':28}},
        ]}
    monkeypatch.setattr(main, 'propose', fake_planner)
    connect(client, 'device_demo')
    cid = client.post('/v1/conversations', json={}).json()['id']
    result = client.post(f'/v1/conversations/{cid}/messages', json={'content':'Pantau suhu setiap 30 detik 3 kali'}).json()
    assert result['task_id']
    assert len(calls) == 2 and 'Field kondisi' in calls[1]
    task = client.get(f"/v1/tasks/{result['task_id']}").json()
    assert task['status'] == 'awaiting_approval'
    assert task['plan']['schedule'] == {'interval_seconds':30,'max_runs':3}


def test_pause_resume_preserves_progress_and_approval(client):
    from app.storage import connect as db_connect
    connect(client, 'device_demo')
    body = {'instruction':'Pantau', 'schedule':{'interval_seconds':1,'max_runs':2}, 'explicit_steps':[{'capability':'device.read_temperature','arguments':{}}]}
    task = client.post('/v1/tasks', json=body).json()
    path = f"/v1/tasks/{task['id']}"
    assert client.post(path+'/resume').status_code == 409
    assert client.post(path+'/pause').status_code == 409
    assert client.post(path+'/approve', json={'version':1}).status_code == 200
    assert run_one()
    assert client.post(path+'/pause').json()['status'] == 'paused'
    assert client.post(path+'/pause').status_code == 409
    with db_connect() as db:
        db.execute("UPDATE schedules SET next_run='2000-01-01T00:00:00+00:00' WHERE task_id=?", (task['id'],))
    assert not run_one()
    assert client.post(path+'/resume').json()['status'] == 'scheduled'
    assert run_one()
    assert client.get(path).json()['result']['runs_completed'] == 2
    assert client.post(path+'/resume').status_code == 409
    events = [event['type'] for event in client.get(path+'/events').json()]
    assert 'task.paused.v1' in events and 'task.resumed.v1' in events


def test_paused_task_can_be_cancelled_or_edited(client):
    connect(client, 'device_demo')
    task = create(client, 'device.read_temperature').json()
    path = f"/v1/tasks/{task['id']}"
    client.post(path+'/approve', json={'version':1})
    client.post(path+'/pause')
    response = client.patch(path+'/schedule', json={'version':1,'schedule':{'interval_seconds':60,'max_runs':2}})
    assert response.json()['status'] == 'awaiting_approval'
    assert client.post(path+'/resume').status_code == 409
    assert client.post(path+'/approve', json={'version':2}).status_code == 200
    client.post(path+'/pause')
    assert client.post(path+'/cancel').json()['status'] == 'cancelled'
    assert not run_one()


def test_external_event_monitor_and_escalation(client):
    source = client.post('/v1/sources', json={'name':'Suhu','kind':'iot'}).json()
    sid = source['id']
    headers = {'Authorization': 'Bearer '+source['token']}
    assert client.post(f'/v1/ingest/{sid}', headers=headers, json={'type':'sensor.reading','data':{'temperature':32}}).status_code == 202
    body = {'instruction':'Pantau suhu', 'explicit_steps':[
        {'capability':'external.latest_event','arguments':{'source_id':sid}},
        {'capability':'external.escalate','arguments':{'message':'Suhu tinggi'},'condition':{'step':0,'field':'data.temperature','operator':'gt','value':30}},
    ]}
    task = client.post('/v1/tasks', json=body).json()
    assert task['status'] == 'awaiting_approval'
    assert client.post(f"/v1/tasks/{task['id']}/approve", json={'version':1}).status_code == 200
    assert run_one()
    result = client.get(f"/v1/tasks/{task['id']}").json()
    assert result['status'] == 'completed'
    assert result['result']['steps'][0]['result']['data']['temperature'] == 32
    assert any(e['type']=='task.escalated.v1' for e in client.get(f"/v1/tasks/{task['id']}/events").json())


def test_external_data_missing_stale_or_revoked_is_not_verified(client):
    from app.storage import connect as db_connect
    source = client.post('/v1/sources', json={'name':'A','kind':'iot'}).json()
    sid = source['id']
    body = {'instruction':'Baca sumber', 'explicit_steps':[{'capability':'external.latest_event','arguments':{'source_id':sid}}]}
    task = client.post('/v1/tasks', json=body).json()
    client.post(f"/v1/tasks/{task['id']}/approve", json={'version':1})
    assert run_one()
    assert 'belum mengirim' in client.get(f"/v1/tasks/{task['id']}").json()['result']['error']
    client.post(f'/v1/ingest/{sid}', headers={'Authorization':'Bearer '+source['token']}, json={'type':'state','data':{'value':1}})
    with db_connect() as db:
        db.execute("UPDATE source_events SET received_at='2000-01-01T00:00:00+00:00' WHERE source_id=?", (sid,))
    task = client.post('/v1/tasks', json=body).json()
    client.post(f"/v1/tasks/{task['id']}/approve", json={'version':1})
    assert run_one()
    assert 'lebih dari 5 menit' in client.get(f"/v1/tasks/{task['id']}").json()['result']['error']
    client.delete(f'/v1/sources/{sid}')
    assert client.post('/v1/tasks', json=body).status_code == 422


def test_home_assistant_numeric_state_and_unavailable(monkeypatch):
    import sys
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent / 'gateways'))
    import home_assistant
    data = home_assistant.normalize_state('sensor.room', {'state':'29.5','attributes':{'unit_of_measurement':'°C'},'last_updated':'2026-01-01T00:00:00Z'})
    assert data['state'] == '29.5' and data['value'] == 29.5 and data['unit'] == '°C'
    assert 'value' not in home_assistant.normalize_state('switch.a', {'state':'on'})
    with pytest.raises(ValueError):
        home_assistant.normalize_state('sensor.room', {'state':'unavailable'})


def test_planner_sees_source_fields_without_values(client, monkeypatch):
    from app import main
    captured = []
    def fake_planner(instruction, capabilities, history=None):
        captured.extend(capabilities)
        return {'answer':'Siap', 'steps':[]}
    monkeypatch.setattr(main, 'propose', fake_planner)
    source = client.post('/v1/sources', json={'name':'Sensor','kind':'iot'}).json()
    client.post(f"/v1/ingest/{source['id']}", headers={'Authorization':'Bearer '+source['token']}, json={'type':'mqtt.message','data':{'payload':{'temperature':32,'serial':'private-value'}}})
    cid = client.post('/v1/conversations', json={}).json()['id']
    client.post(f'/v1/conversations/{cid}/messages', json={'content':'Pantau suhu'})
    capability = next(item for item in captured if item['name'] == 'external.latest_event')
    assert {'field':'data.payload.temperature','type':'number'} in capability['available_sources'][0]['observed_fields']
    assert 'private-value' not in str(capability)


def test_nonstandard_json_values_rejected(client):
    source = client.post('/v1/sources', json={'name':'Sensor','kind':'iot'}).json()
    headers = {'Authorization':'Bearer '+source['token'], 'Content-Type':'application/json'}
    response = client.post(f"/v1/ingest/{source['id']}", headers=headers, content='{"type":"reading","data":{"value":NaN}}')
    assert response.status_code == 422
    assert client.get(f"/v1/sources/{source['id']}/events").json() == []


def test_condition_rejects_incompatible_data_types():
    from app.service import matches, validate_steps
    with pytest.raises(ValueError, match='Jenis data'):
        matches({'step':0,'field':'value','operator':'ne','value':1}, [{'result':{'value':'1'}}])
    with pytest.raises(ValueError, match='Jenis data'):
        matches({'step':0,'field':'value','operator':'eq','value':1}, [{'result':{'value':True}}])
    with pytest.raises(ValueError, match='Nilai kondisi'):
        validate_steps([{'capability':'device.read_temperature','arguments':{}},{'capability':'device.turn_on_light','arguments':{},'condition':{'step':0,'field':'temperature_c','operator':'gt','value':[28]}}], {'device_demo'})


def test_webhook_lease_crash_respects_maximum_attempts(client, monkeypatch):
    from app import webhooks
    from app.storage import connect as db_connect
    sub = client.post('/v1/webhook-subscriptions', json={'url':'https://example.com/hook'}).json()
    connect(client, 'device_demo')
    create(client, 'device.read_temperature')
    with db_connect() as db:
        db.execute("UPDATE deliveries SET status='sending', attempts=5, next_attempt='2000-01-01T00:00:00+00:00'")
    monkeypatch.setattr(webhooks, 'post_pinned', lambda *args: pytest.fail('expired max-attempt lease must not be sent'))
    assert not webhooks.deliver_one()
    deliveries = client.get('/v1/webhook-deliveries').json()
    assert deliveries and all(item['status']=='failed' for item in deliveries)


def test_concurrent_task_creation_is_idempotent(client):
    from concurrent.futures import ThreadPoolExecutor
    connect(client, 'device_demo')
    def submit(_):
        return create(client, 'device.read_temperature', headers={'Idempotency-Key':'same-request'})
    with ThreadPoolExecutor(max_workers=6) as executor:
        responses = list(executor.map(submit, range(6)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()['id'] for response in responses}) == 1
    assert len(client.get('/v1/tasks').json()) == 1


def test_webhook_rejects_private_or_mixed_dns(monkeypatch):
    import socket
    from app.webhooks import public_ip, validate_url
    for url in ['http://example.com', 'https://user:pass@example.com', 'https://example.com:8443']:
        with pytest.raises(ValueError):
            validate_url(url)
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: [(None, None, None, None, ('8.8.8.8',443)), (None, None, None, None, ('127.0.0.1',443))])
    with pytest.raises(ValueError):
        public_ip('example.com')


def test_ingest_payload_limit_and_disabled_source(client):
    source = client.post('/v1/sources', json={'name':'Sensor','kind':'iot'}).json()
    headers = {'Authorization':'Bearer '+source['token'], 'Content-Type':'application/json'}
    result = client.post(f"/v1/ingest/{source['id']}", headers=headers, content='{"type":"reading","data":{"value":"' + 'x'*33000 + '"}}')
    assert result.status_code == 413
    assert not client.get(f"/v1/sources/{source['id']}/events").json()


def test_notification_and_rerun_require_fresh_approval(client):
    connect(client, 'device_demo')
    task = create(client, 'device.read_temperature').json()
    tid = task['id']
    assert client.post(f'/v1/tasks/{tid}/rerun').status_code == 409
    client.post(f'/v1/tasks/{tid}/approve', json={'version':1})
    assert run_one()
    notifications = client.get('/v1/notifications').json()
    completed = next(item for item in notifications if item['type']=='task.completed.v1' and item['task_id']==tid)
    assert not completed['is_read']
    assert client.post(f"/v1/notifications/{completed['id']}/read").status_code == 200
    assert client.post(f"/v1/notifications/{completed['id']}/read").status_code == 200
    assert next(item for item in client.get('/v1/notifications').json() if item['id']==completed['id'])['is_read']
    rerun = client.post(f'/v1/tasks/{tid}/rerun')
    assert rerun.status_code == 201
    fresh = rerun.json()
    assert fresh['id'] != tid and fresh['plan']['rerun_of'] == tid
    assert fresh['status'] == 'awaiting_approval' and fresh['result'] is None
    assert not run_one()
    assert client.post(f"/v1/tasks/{fresh['id']}/approve", json={'version':1}).status_code == 200
    assert run_one()
    assert client.get(f"/v1/tasks/{fresh['id']}").json()['status']=='completed'


def test_failed_task_notification_and_rerun_checks_source(client):
    source = client.post('/v1/sources', json={'name':'Sensor','kind':'iot'}).json()
    task = client.post('/v1/tasks', json={'instruction':'Pantau', 'explicit_steps':[{'capability':'external.latest_event','arguments':{'source_id':source['id']}}]}).json()
    client.post(f"/v1/tasks/{task['id']}/approve", json={'version':1})
    assert run_one()
    failed = next(n for n in client.get('/v1/notifications').json() if n['type']=='task.failed.v1')
    assert 'belum mengirim' in failed['task_result']['error']
    client.delete(f"/v1/sources/{source['id']}")
    assert client.post(f"/v1/tasks/{task['id']}/rerun").status_code == 422
    assert client.post('/v1/notifications/does-not-exist/read').status_code == 404


def test_rerun_is_added_to_original_conversation(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'propose', lambda *args: {'answer':'Siap', 'steps':[{'capability':'device.read_temperature','arguments':{}}]})
    connect(client, 'device_demo')
    cid = client.post('/v1/conversations', json={}).json()['id']
    original = client.post(f'/v1/conversations/{cid}/messages', json={'content':'Periksa suhu'}).json()['task_id']
    assert run_one()
    rerun = client.post(f'/v1/tasks/{original}/rerun').json()
    messages = client.get(f'/v1/conversations/{cid}/messages').json()
    assert messages[-1]['task_id'] == rerun['id']
    assert messages[-1]['task']['status'] == 'awaiting_approval'


def test_unread_count_includes_notifications_beyond_recent_list(client):
    from app.storage import connect as db_connect, event
    with db_connect() as db:
        for _ in range(105):
            event(db, 'default', 'task-example', 'task.completed.v1', {})
    assert len(client.get('/v1/notifications').json()) == 100
    assert client.get('/v1/notifications/unread-count').json()['count'] == 105
    item = client.get('/v1/notifications').json()[0]
    client.post(f"/v1/notifications/{item['id']}/read")
    assert client.get('/v1/notifications/unread-count').json()['count'] == 104
    assert client.post('/v1/notifications/read-all').status_code == 200
    assert client.get('/v1/notifications/unread-count').json()['count'] == 0
