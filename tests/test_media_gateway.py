import asyncio
import io
import json
import wave
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import media


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('KANCA_DB_PATH', str(tmp_path / 'media.db'))
    monkeypatch.setenv('KANCA_API_KEY', 'admin-key')
    with TestClient(app, headers={'X-API-Key':'admin-key'}) as c:
        yield c


def wav_data():
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000); audio.writeframes(b'\x00\x00' * 1600)
    return output.getvalue()


def test_media_opt_in_and_token_enforcement(client, monkeypatch):
    source = client.post('/v1/sources', json={'name':'Kamera','kind':'camera'}).json()
    sid, token = source['id'], source['token']
    calls = []
    async def fake_analyze(kind, raw, mime, prompt):
        calls.append((kind, mime, prompt))
        return {'summary':'Terlihat tiga dus', 'count':3, 'uncertain':False, 'note':'Perkiraan'}
    monkeypatch.setattr(media, 'analyze', fake_analyze)
    headers = {'Authorization':'Bearer '+token}
    image = b'\xff\xd8\xfftest\xff\xd9'
    assert client.post(f'/v1/ingest/{sid}/media?media_type=vision', headers=headers, content=image).status_code == 401
    settings = {'vision_enabled':True,'audio_enabled':False,'vision_prompt':'Hitung dus', 'audio_prompt':'Rangkum suara'}
    assert client.put(f'/v1/sources/{sid}/media-settings', json=settings).status_code == 200
    assert client.post(f'/v1/ingest/{sid}/media?media_type=vision', headers={'Authorization':'Bearer wrong'}, content=image).status_code == 401
    assert client.post(f'/v1/ingest/{sid}/media?media_type=audio', headers=headers, content=wav_data()).status_code == 403
    assert client.post(f'/v1/ingest/{sid}/media?media_type=vision', headers=headers, content=b'not-image').status_code == 422
    result = client.post(f'/v1/ingest/{sid}/media?media_type=vision', headers=headers, content=image)
    assert result.status_code == 202 and result.json()['result']['count'] == 3
    assert calls == [('vision','image/jpeg','Hitung dus')]
    event = client.get(f'/v1/sources/{sid}/events').json()[0]
    assert event['event_type'] == 'media.vision' and event['payload']['count'] == 3
    assert 'test' not in json.dumps(event)


@pytest.mark.parametrize('kind,mime,prefix', [('vision','image/jpeg','image_url'),('audio','audio/wav','audio_url')])
def test_baseten_media_request_shape(monkeypatch, kind, mime, prefix):
    monkeypatch.setenv('BASETEN_API_KEY','provider-secret')
    seen = []
    async def mock_post(self, url, **kwargs):
        seen.append((url, kwargs))
        return httpx.Response(200, json={'choices':[{'message':{'content':'{"summary":"ok","count":3,"uncertain":true}'}}]}, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx.AsyncClient, 'post', mock_post)
    result = asyncio.run(media.analyze(kind,b'sample',mime,'Test'))
    part = seen[0][1]['json']['messages'][1]['content'][1]
    assert part['type'] == prefix and part[prefix]['url'].startswith('data:'+mime+';base64,')
    assert seen[0][1]['headers']['Authorization'] == 'Bearer provider-secret'
    assert result['count'] is None


def test_audio_validation():
    assert media.validate_media('audio', wav_data()) == 'audio/wav'
    with pytest.raises(ValueError): media.validate_media('audio', b'invalid')


def test_source_disabled_during_analysis_does_not_store_result(client, monkeypatch):
    from app.storage import connect
    source = client.post('/v1/sources', json={'name':'Kamera','kind':'camera'}).json()
    sid = source['id']
    client.put(f'/v1/sources/{sid}/media-settings', json={'vision_enabled':True})
    async def disable_during_analysis(*args):
        with connect() as db:
            db.execute("UPDATE sources SET status='disabled' WHERE id=?", (sid,))
        return {'summary':'ok','count':1,'uncertain':False}
    monkeypatch.setattr(media, 'analyze', disable_during_analysis)
    response = client.post(f'/v1/ingest/{sid}/media?media_type=vision', headers={'Authorization':'Bearer '+source['token']}, content=b'\xff\xd8\xffx\xff\xd9')
    assert response.status_code == 401
    assert client.get(f'/v1/sources/{sid}/events').json() == []


def test_multiple_media_types_require_explicit_event_type(client):
    from app.service import run_one
    source = client.post('/v1/sources', json={'name':'Kamera','kind':'camera'}).json()
    sid = source['id']
    headers = {'Authorization':'Bearer '+source['token']}
    for kind in ('media.vision','media.audio'):
        client.post(f'/v1/ingest/{sid}', headers=headers, json={'type':kind,'data':{'count':3}})
    body = {'instruction':'Baca','explicit_steps':[{'capability':'external.latest_event','arguments':{'source_id':sid}}]}
    task = client.post('/v1/tasks', json=body).json()
    client.post(f"/v1/tasks/{task['id']}/approve", json={'version':1})
    assert run_one()
    assert 'beberapa jenis' in client.get(f"/v1/tasks/{task['id']}").json()['result']['error']
    body['explicit_steps'][0]['arguments']['event_type'] = 'media.vision'
    task = client.post('/v1/tasks', json=body).json()
    client.post(f"/v1/tasks/{task['id']}/approve", json={'version':1})
    assert run_one()
    assert client.get(f"/v1/tasks/{task['id']}").json()['result']['steps'][0]['result']['event_type'] == 'media.vision'


def test_gateway_config_rejects_insecure_remote(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('mini_gateway', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'gateway.py')
    gateway = importlib.util.module_from_spec(spec); spec.loader.exec_module(gateway)
    path = tmp_path / 'config.json'
    config = {'server_url':'http://example.com','source_id':'src_a','source_token':'token','camera_url':'rtsp://camera','interval_seconds':60,'audio_enabled':False}
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError): gateway.load_config(path)
    config['server_url'] = 'https://example.com'
    path.write_text(json.dumps(config))
    assert gateway.load_config(path)['source_id'] == 'src_a'


def test_gateway_multiple_sources_and_legacy_config(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('mini_gateway_multi', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'gateway.py')
    gateway = importlib.util.module_from_spec(spec); spec.loader.exec_module(gateway)
    path = tmp_path / 'config.json'
    config = {'server_url':'https://kanca.example','sources':[
        {'type':'mqtt','source_id':'src_a','source_token':'a','mqtt_host':'broker','mqtt_topic':'room/temp','mqtt_port':8883},
        {'type':'home_assistant','source_id':'src_b','source_token':'b','ha_url':'http://homeassistant:8123','ha_token':'ha','ha_entity':'sensor.room','interval_seconds':30},
        {'type':'camera','source_id':'src_c','source_token':'c','camera_url':'rtsp://camera/stream','interval_seconds':60,'audio_enabled':False},
    ]}
    path.write_text(json.dumps(config))
    assert [s['type'] for s in gateway.load_config(path)['sources']] == ['mqtt','home_assistant','camera']
    config['sources'][1]['source_id']='src_a'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError): gateway.load_config(path)
    config = {'server_url':'https://kanca.example','source_id':'src_old','source_token':'token','camera_url':'rtsp://camera','interval_seconds':60,'audio_enabled':False}
    path.write_text(json.dumps(config))
    assert gateway.load_config(path)['sources'][0]['type']=='camera'


def test_gateway_iot_normalization_and_forwarding(monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('mini_gateway_iot', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'gateway.py')
    gateway = importlib.util.module_from_spec(spec); spec.loader.exec_module(gateway)
    assert gateway.normalize_ha('sensor.temp', {'state':'29.5','attributes':{'unit_of_measurement':'°C'}})['value'] == 29.5
    with pytest.raises(ValueError): gateway.normalize_ha('sensor.temp', {'state':'unavailable'})
    with pytest.raises(ValueError): gateway.normalize_ha('sensor.temp', {'state':'29.5','attributes':None})
    with pytest.raises(ValueError): gateway.normalize_ha('sensor.temp', {'state':'29.5','attributes':[]})
    with pytest.raises(ValueError): gateway.normalize_ha('sensor.temp', [])
    assert gateway.mqtt_payload(SimpleNamespace(retain=True, payload=b'{}', topic='room')) is None
    data = gateway.mqtt_payload(SimpleNamespace(retain=False, payload=b'{"temperature":29}', topic='room'))
    assert data['payload']['temperature'] == 29
    with pytest.raises(ValueError): gateway.mqtt_payload(SimpleNamespace(retain=False, payload=b'[]', topic='room'))
    sent = []
    class FakeResponse:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def fake_open(request, timeout):
        sent.append(request)
        return FakeResponse()
    monkeypatch.setattr(gateway.no_redirect, 'open', fake_open)
    config = {'server_url':'https://kanca.example','source_id':'src_a','source_token':'source-secret'}
    assert gateway.send_event(config, 'mqtt.message', data) == 202
    assert sent[0].full_url == 'https://kanca.example/v1/ingest/src_a'
    assert sent[0].get_header('Authorization') == 'Bearer source-secret'
    assert json.loads(sent[0].data)['data']['payload']['temperature'] == 29


def test_gateway_http_json_and_custom_connectors(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('mini_gateway_http', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'gateway.py')
    gateway = importlib.util.module_from_spec(spec); spec.loader.exec_module(gateway)
    path = tmp_path / 'config.json'
    cfg = {'server_url':'https://kanca.example','sources':[
        {'type':'http_json','source_id':'src_http','source_token':'s','http_url':'https://device.example/data','http_token':'device-secret','interval_seconds':60},
        {'type':'custom','source_id':'src_custom','source_token':'c'},
    ]}
    path.write_text(json.dumps(cfg))
    assert len(gateway.load_config(path)['sources']) == 2
    cfg['sources'][0]['http_url']='http://device.example/data'
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError): gateway.load_config(path)
    requests = []
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"temperature":29}'
    def fake_open(req, timeout):
        requests.append(req)
        return FakeResponse()
    monkeypatch.setattr(gateway.no_redirect, 'open', fake_open)
    assert gateway.read_http_json({'http_url':'https://device.example/data','http_token':'device-secret'}) == {'temperature':29}
    assert requests[0].get_header('Authorization') == 'Bearer device-secret'


def test_setup_discovers_home_assistant_entities_without_disclosing_token(monkeypatch):
    import importlib.util
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent / 'mini-pc-gateway'))
    spec = importlib.util.spec_from_file_location('gateway_setup_test', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'setup.py')
    setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
    sent = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            return json.dumps([{'entity_id':'sensor.temperature','attributes':{'friendly_name':'Suhu'}}, {'entity_id':'switch.light','attributes':{}}, {'entity_id':'bad/escape'}]).encode()
    class Opener:
        def open(self, request, timeout):
            sent.append(request)
            return Response()
    results = setup.discover_home_assistant('https://ha.example', 'private-secret', opener=Opener())
    assert results == [{'entity_id':'sensor.temperature','name':'Suhu'}, {'entity_id':'switch.light','name':'switch.light'}]
    assert sent[0].full_url == 'https://ha.example/api/states'
    assert sent[0].get_header('Authorization') == 'Bearer private-secret'
    assert 'private-secret' not in str(results)


def test_direct_ble_config_and_decoding(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('mini_gateway_ble', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'gateway.py')
    gateway = importlib.util.module_from_spec(spec); spec.loader.exec_module(gateway)
    source = {'type':'ble','source_id':'src_ble','source_token':'secret','ble_address':'AA:BB:CC:DD:EE:FF','ble_profile':'battery','ble_characteristic':'00002a19-0000-1000-8000-00805f9b34fb','interval_seconds':60}
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'server_url':'https://kanca.example','sources':[source]}))
    assert gateway.load_config(path)['sources'][0]['type'] == 'ble'
    assert gateway.decode_ble('battery', b'\x64') == {'value':100, 'unit':'percent'}
    assert gateway.decode_ble('raw', b'\x01\xff') == {'raw_hex':'01ff'}
    with pytest.raises(ValueError): gateway.decode_ble('battery', b'\xff')
    source['ble_characteristic'] = '00002a6e-0000-1000-8000-00805f9b34fb'
    path.write_text(json.dumps({'server_url':'https://kanca.example','sources':[source]}))
    with pytest.raises(ValueError): gateway.load_config(path)


def test_direct_ble_read_with_simulated_device(monkeypatch):
    import importlib.util
    import sys
    from types import SimpleNamespace
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('mini_gateway_ble_mock', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'gateway.py')
    gateway = importlib.util.module_from_spec(spec); spec.loader.exec_module(gateway)
    class FakeClient:
        def __init__(self, address, timeout): assert address == 'AA:BB:CC:DD:EE:FF'
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def read_gatt_char(self, characteristic): return b'\x4b'
    monkeypatch.setitem(sys.modules, 'bleak', SimpleNamespace(BleakClient=FakeClient))
    config = {'ble_address':'AA:BB:CC:DD:EE:FF','ble_profile':'battery','ble_characteristic':'00002a19-0000-1000-8000-00805f9b34fb'}
    assert asyncio.run(gateway.read_ble_once(config))['value'] == 75


def test_gateway_detect_inventory_reports_candidates_without_claiming_support(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('gateway_detect_test', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'detect.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    usb = tmp_path/'usb'; device = usb/'1-1'; device.mkdir(parents=True)
    for name, value in {'idVendor':'1234','idProduct':'abcd','manufacturer':'Example','product':'Zigbee USB Radio','bDeviceClass':'00'}.items():
        (device/name).write_text(value)
    serial = tmp_path/'serial'; serial.mkdir(); (serial/'usb-radio').touch()
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0,stdout='Controller AA:BB'))
    result = module.detect(usb, serial)
    assert result['usb_devices'][0]['protocol_candidates'] == ['Zigbee']
    assert result['usb_devices'][0]['vendor_id'] == '1234'
    assert result['bluetooth_controller'] == 'available'
    assert result['serial_devices'] == [str(serial/'usb-radio')]


def test_setup_ble_discovery_selection(monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent / 'mini-pc-gateway'))
    spec = importlib.util.spec_from_file_location('gateway_setup_ble_test', Path(__file__).resolve().parent.parent / 'mini-pc-gateway' / 'setup.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout='AA:BB:CC:DD:EE:FF  Example sensor\n'))
    inputs = iter(['', '1'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    assert module.choose_ble_address() == 'AA:BB:CC:DD:EE:FF'
