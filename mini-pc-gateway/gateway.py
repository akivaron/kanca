"""Capture small samples and send only to Kanca. No model credentials are used here."""
import json
import os
import subprocess
import tempfile
import threading
import time
import math
import ssl
import re
import uuid
import asyncio
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024
MAX_SOURCES = 512
PUBLIC_HLS_HOSTS = {
    'dki-jkt.balitower.co.id',
    'cctvjss.jogjakota.go.id',
    'stream.bantulkab.go.id',
    'stream.gunungkidulkab.go.id',
    'atcs-dishubkbb.urbanaccess.net',
    'atcs.tanahbumbukab.go.id',
    'camera.jtd.co.id',
    'cctv-dishub.sukabumikab.go.id',
    'cctv-dishub.tangerangkab.go.id',
    'cctv.cirebonkota.go.id',
    'cctv.ctptollways.com',
    'cctv.garutkab.go.id',
    'cctv.rembangkab.go.id',
    'cctvjorrw1.com',
    'cctvstream.badilag.net',
    'dev.cctv.magelangkota.go.id',
    'dishub.depok.go.id',
    'info.serbaraja-tollroad.co.id',
    'its.binamarga.pu.go.id',
    'pelindung.bandung.go.id',
    'pptrlive.co.id',
    'pub.hk-opt.com',
    'pub2.hk-opt.com',
    'restreamer.kotabogor.go.id',
    'restreamer2.kotabogor.go.id',
    'restreamer3.kotabogor.go.id',
    'restreamer4.kotabogor.go.id',
    'restreamer5.kotabogor.go.id',
    'rstp2hls.metrokota.go.id',
    'streaming-cct.co.id',
    'transcode.baliprov.go.id',
}
PUBLIC_HLS_PORTS = {
    'dki-jkt.balitower.co.id': {7028},
    'cctvjss.jogjakota.go.id': {443},
    'stream.bantulkab.go.id': {443},
    'stream.gunungkidulkab.go.id': {8888},
    'atcs-dishubkbb.urbanaccess.net': {443},
    'atcs.tanahbumbukab.go.id': {443},
    'camera.jtd.co.id': {443},
    'cctv-dishub.sukabumikab.go.id': {443},
    'cctv-dishub.tangerangkab.go.id': {443},
    'cctv.cirebonkota.go.id': {443},
    'cctv.ctptollways.com': {2254},
    'cctv.garutkab.go.id': {443},
    'cctv.rembangkab.go.id': {443},
    'cctvjorrw1.com': {443},
    'cctvstream.badilag.net': {443},
    'dev.cctv.magelangkota.go.id': {443},
    'dishub.depok.go.id': {443},
    'info.serbaraja-tollroad.co.id': {20443},
    'its.binamarga.pu.go.id': {8989},
    'pelindung.bandung.go.id': {3443},
    'pptrlive.co.id': {443},
    'pub.hk-opt.com': {443},
    'pub2.hk-opt.com': {443},
    'restreamer.kotabogor.go.id': {443},
    'restreamer2.kotabogor.go.id': {443},
    'restreamer3.kotabogor.go.id': {443},
    'restreamer4.kotabogor.go.id': {443},
    'restreamer5.kotabogor.go.id': {443},
    'rstp2hls.metrokota.go.id': {443},
    'streaming-cct.co.id': {443},
    'transcode.baliprov.go.id': {443},
}
_bmkg_request_lock = threading.Lock()
_last_bmkg_request_at = 0.0


def load_config(path):
    config = json.loads(Path(path).read_text())
    parsed = urllib.parse.urlparse(config.get('server_url', ''))
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1', 'host.docker.internal'))):
        raise ValueError('Kanca URL must use HTTPS, except localhost for testing')
    if 'sources' not in config:
        config['sources'] = [{**{k:v for k,v in config.items() if k != 'server_url'}, 'type':'camera'}]
    sources = config['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise ValueError(f'Configuration must have 1–{MAX_SOURCES} sources')
    ids = set()
    for source in sources:
        if (not isinstance(source, dict)
                or not isinstance(source.get('source_id'), str) or not source['source_id'].strip()
                or not isinstance(source.get('source_token'), str) or not source['source_token']
                or source['source_id'] in ids):
            raise ValueError('ID dan token sources wajib unik')
        if 'on_demand' in source and type(source['on_demand']) is not bool:
            raise ValueError('Pengaturan on_demand must be boolean')
        if 'name' in source and (not isinstance(source['name'], str) or not 1 <= len(source['name'].strip()) <= 100):
            raise ValueError('Name sources invalid')
        ids.add(source['source_id'])
        kind = source.get('type')
        if kind in ('camera', 'home_assistant', 'http_json', 'ble') and (type(source.get('interval_seconds')) is not int or not 10 <= source['interval_seconds'] <= 86400):
            raise ValueError('Interval invalid')
        if kind == 'camera':
            camera_url = urllib.parse.urlparse(str(source.get('camera_url', '')))
            rtsp_camera = camera_url.scheme in ('rtsp', 'rtsps') and bool(camera_url.hostname)
            public_hls_camera = (camera_url.scheme == 'https' and camera_url.hostname in PUBLIC_HLS_HOSTS
                                 and camera_url.path.endswith('.m3u8') and not camera_url.username
                                 and not camera_url.password and not camera_url.query and not camera_url.fragment
                                 and (camera_url.port or 443) in PUBLIC_HLS_PORTS.get(camera_url.hostname, set()))
            if not (rtsp_camera or public_hls_camera) or type(source.get('audio_enabled', False)) is not bool:
                raise ValueError('Configuration kamera invalid')
        elif kind == 'mqtt':
            if not source.get('mqtt_host') or not source.get('mqtt_topic') or any(c in source['mqtt_topic'] for c in '#+') or type(source.get('mqtt_port', 8883)) is not int or not 1 <= source.get('mqtt_port', 8883) <= 65535:
                raise ValueError('Configuration MQTT invalid')
        elif kind == 'home_assistant':
            url = urllib.parse.urlparse(source.get('ha_url', ''))
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment or not source.get('ha_token') or not source.get('ha_entity'):
                raise ValueError('Configuration Home Assistant invalid')
        elif kind == 'http_json':
            url = urllib.parse.urlparse(source.get('http_url', ''))
            event_type = source.get('event_type', 'http.json')
            if not isinstance(event_type, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', event_type) or url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.fragment or (source.get('http_token') and url.scheme != 'https'):
                raise ValueError('Configuration HTTP JSON invalid; bearer token memerlukan HTTPS')
        elif kind == 'custom':
            pass
        elif kind == 'ble':
            address = source.get('ble_address')
            if not isinstance(address, str) or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', address) or source.get('ble_profile') not in ('raw','battery'):
                raise ValueError('Configuration Bluetooth invalid')
            try:
                characteristic = uuid.UUID(source.get('ble_characteristic', ''))
            except (ValueError, AttributeError, TypeError) as exc:
                raise ValueError('UUID Bluetooth invalid') from exc
            if source['ble_profile'] == 'battery' and str(characteristic) != '00002a19-0000-1000-8000-00805f9b34fb':
                raise ValueError('Profil baterai memerlukan characteristic baterai standar')
        else:
            raise ValueError('Unsupported source type')
    return config


def source_label(config):
    return config.get('name') or config['source_id']


def capture(config, kind):
    suffix = '.jpg' if kind == 'vision' else '.wav'
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        cmd = ['ffmpeg','-nostdin','-v','error','-y']
        camera_scheme = urllib.parse.urlparse(config['camera_url']).scheme
        if camera_scheme in ('rtsp', 'rtsps'):
            cmd += ['-rtsp_transport','tcp']
        elif camera_scheme == 'https':
            if urllib.parse.urlparse(config['camera_url']).hostname == 'dki-jkt.balitower.co.id':
                # BaliTower HLS fragments use a provider-specific .hls.fmp4 suffix.
                cmd += ['-extension_picky','0']
        cmd += ['-i',config['camera_url']]
        if kind == 'vision':
            cmd += ['-frames:v','1','-vf','scale=1280:720:force_original_aspect_ratio=decrease','-q:v','4',path]
        else:
            cmd += ['-t','5','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',path]
        subprocess.run(cmd, check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.getsize(path) > MAX_BYTES:
            raise ValueError('Cuplikan melebihi batas ukuran')
        return Path(path).read_bytes()
    finally:
        try: os.unlink(path)
        except FileNotFoundError: pass


def send(config, kind, raw):
    source = urllib.parse.quote(config['source_id'], safe='')
    endpoint = config['server_url'].rstrip('/') + '/v1/ingest/' + source + '/media?media_type=' + kind
    request = urllib.request.Request(endpoint, data=raw, method='POST', headers={'Authorization':'Bearer ' + config['source_token'], 'Content-Type':'application/octet-stream'})
    with no_redirect.open(request, timeout=100) as response:
        return response.status


class BlockRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


no_redirect = urllib.request.build_opener(BlockRedirect())


def send_event(config, event_type, data):
    source = urllib.parse.quote(config['source_id'], safe='')
    endpoint = config['server_url'].rstrip('/') + '/v1/ingest/' + source
    payload = json.dumps({'type':event_type, 'data':data}, allow_nan=False).encode()
    if len(payload) > 32768:
        raise ValueError('Event terlalu besar')
    request = urllib.request.Request(endpoint, data=payload, method='POST', headers={'Authorization':'Bearer ' + config['source_token'], 'Content-Type':'application/json'})
    with no_redirect.open(request, timeout=15) as response:
        return response.status


def source_status(config):
    endpoint = config['server_url'].rstrip('/') + '/v1/ingest/' + urllib.parse.quote(config['source_id'], safe='') + '/status'
    request = urllib.request.Request(endpoint, headers={'Authorization':'Bearer ' + config['source_token']})
    try:
        with no_redirect.open(request, timeout=10) as response:
            raw = response.read(1025)
        if len(raw) > 1024:
            return {}
        status = json.loads(raw)
        return status if isinstance(status, dict) else {}
    except (OSError, ValueError, urllib.error.URLError):
        # Fail closed: never capture or poll source data if Kanca cannot confirm activation.
        return {}


def source_is_active(config):
    return source_status(config).get('active') is True


def normalize_ha(entity, state):
    if not isinstance(state, dict):
        raise ValueError('Response Home Assistant invalid')
    raw = state['state']
    if not isinstance(raw, str) or raw in ('unknown', 'unavailable'):
        raise ValueError('State unavailable')
    attributes = state.get('attributes', {})
    if not isinstance(attributes, dict):
        raise ValueError('Atribut Home Assistant invalid')
    result = {'entity_id':entity, 'state':raw, 'unit':attributes.get('unit_of_measurement'), 'last_updated':state.get('last_updated')}
    try:
        value = float(raw)
        if math.isfinite(value): result['value'] = value
    except ValueError:
        pass
    return result


def mqtt_payload(message):
    if message.retain:
        return None
    if len(message.payload) > 24000:
        raise ValueError('Pesan MQTT terlalu besar')
    payload = json.loads(message.payload)
    if not isinstance(payload, dict):
        raise ValueError('Payload must be an object')
    return {'topic':message.topic, 'payload':payload}


def run_camera(config):
    next_automation_at = 0.0
    while True:
        status = source_status(config)
        if status.get('active') is not True:
            time.sleep(10 if config.get('on_demand') else min(config['interval_seconds'], 60))
            continue
        requested = status.get('capture_requested') is True
        automated = status.get('automation_enabled') is True
        if config.get('on_demand') and not requested and not automated:
            time.sleep(5)
            continue
        if automated and not requested and time.monotonic() < next_automation_at:
            time.sleep(min(5, max(0.2, next_automation_at - time.monotonic())))
            continue
        enabled_kinds = []
        if status.get('vision_enabled') is True:
            enabled_kinds.append('vision')
        if config.get('audio_enabled') and status.get('audio_enabled') is True:
            enabled_kinds.append('audio')
        if not enabled_kinds:
            time.sleep(5 if config.get('on_demand') or automated else min(config['interval_seconds'], 60))
            continue
        for kind in enabled_kinds:
            try:
                send(config, kind, capture(config, kind))
                print(f'camera {source_label(config)}: {kind} sent', flush=True)
            except (OSError, ValueError, subprocess.SubprocessError, urllib.error.URLError) as exc:
                status = getattr(exc, 'code', None)
                print(f'camera {source_label(config)}: {kind} failed' + (f' (HTTP {status})' if status else ''), flush=True)
        if automated:
            next_automation_at = time.monotonic() + status.get('automation_interval_seconds', 30)
        time.sleep(5 if config.get('on_demand') or automated else config['interval_seconds'])


def run_home_assistant(config):
    entity = config['ha_entity']
    url = config['ha_url'].rstrip('/') + '/api/states/' + urllib.parse.quote(entity, safe='.')
    while True:
        if not source_is_active(config):
            time.sleep(min(config['interval_seconds'], 60))
            continue
        try:
            request = urllib.request.Request(url, headers={'Authorization':'Bearer '+config['ha_token']})
            with no_redirect.open(request, timeout=10) as response:
                raw = response.read(65537)
            if len(raw) > 65536: raise ValueError('Response terlalu besar')
            send_event(config, 'home_assistant.state', normalize_ha(entity, json.loads(raw)))
            print(f'home_assistant {source_label(config)}: sent', flush=True)
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
            print(f'home_assistant {source_label(config)}: failed to read or send', flush=True)
        time.sleep(config['interval_seconds'])


def read_http_json(config):
    headers = {'Accept':'application/json', 'User-Agent':'KancaGateway/1.0'}
    if config.get('http_token'):
        headers['Authorization'] = 'Bearer ' + config['http_token']
    global _last_bmkg_request_at
    host = (urllib.parse.urlparse(config['http_url']).hostname or '').lower()
    if host == 'bmkg.go.id' or host.endswith('.bmkg.go.id'):
        with _bmkg_request_lock:
            wait = 1.1 - (time.monotonic() - _last_bmkg_request_at)
            if wait > 0:
                time.sleep(wait)
            _last_bmkg_request_at = time.monotonic()
    request = urllib.request.Request(config['http_url'], headers=headers)
    with no_redirect.open(request, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('Response HTTP terlalu besar')
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Response HTTP must be objek JSON')
    return data


def normalize_http_payload(config, payload):
    if not config.get('event_type', '').startswith('usgs.earthquake.'):
        return payload
    features = payload.get('features')
    if not isinstance(features, list):
        raise ValueError('Feed USGS does not have daftar features')
    events = []
    for feature in features[:50]:
        if not isinstance(feature, dict):
            continue
        properties = feature.get('properties') or {}
        geometry = feature.get('geometry') or {}
        coordinates = geometry.get('coordinates') or []
        item = {
            'magnitude': properties.get('mag'),
            'place': properties.get('place'),
            'time_ms': properties.get('time'),
            'url': properties.get('url'),
        }
        if isinstance(coordinates, list) and len(coordinates) >= 3:
            item.update({'longitude': coordinates[0], 'latitude': coordinates[1], 'depth_km': coordinates[2]})
        events.append({key: value for key, value in item.items() if value is not None})
    return {'count': len(features), 'events': events, 'truncated': len(features) > len(events)}


def run_http_json(config):
    next_automation_at = 0.0
    while True:
        status = source_status(config)
        if status.get('active') is not True:
            time.sleep(10 if config.get('on_demand') else min(config['interval_seconds'], 60))
            continue
        requested = status.get('capture_requested') is True
        automated = status.get('automation_enabled') is True
        if config.get('on_demand') and not requested and not automated:
            time.sleep(5)
            continue
        if automated and not requested and time.monotonic() < next_automation_at:
            time.sleep(min(5, max(0.2, next_automation_at - time.monotonic())))
            continue
        try:
            payload = normalize_http_payload(config, read_http_json(config))
            send_event(config, config.get('event_type', 'http.json'), {'payload': payload})
            print(f'http_json {config["source_id"]}: sent', flush=True)
        except (OSError, ValueError, UnicodeDecodeError, urllib.error.URLError):
            print(f'http_json {config["source_id"]}: failed to read or send', flush=True)
        if automated:
            next_automation_at = time.monotonic() + status.get('automation_interval_seconds', 30)
        time.sleep(5 if config.get('on_demand') or automated else config['interval_seconds'])


def run_mqtt(config):
    import paho.mqtt.client as mqtt
    while True:
        if not source_is_active(config):
            time.sleep(60)
            continue
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            if config.get('mqtt_username'):
                client.username_pw_set(config['mqtt_username'], config.get('mqtt_password', ''))
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            def on_connect(client, userdata, flags, reason_code, properties):
                if reason_code.is_failure:
                    print(f'mqtt {config["source_id"]}: connection rejected', flush=True)
                else:
                    client.subscribe(config['mqtt_topic'], qos=1)
            def on_message(client, userdata, message):
                try:
                    data = mqtt_payload(message)
                    if data is None:
                        print(f'mqtt {config["source_id"]}: retained message skipped', flush=True)
                        return
                    if not source_is_active(config):
                        return
                    send_event(config, 'mqtt.message', data)
                except (ValueError, UnicodeDecodeError, OSError, urllib.error.URLError):
                    print(f'mqtt {config["source_id"]}: message is invalid or could not be sent', flush=True)
            client.on_connect, client.on_message = on_connect, on_message
            client.connect(config['mqtt_host'], config.get('mqtt_port', 8883), 60)
            client.loop_forever(retry_first_connection=True)
        except (OSError, ValueError):
            print(f'mqtt {config["source_id"]}: connection failed; retrying', flush=True)
        time.sleep(10)


def decode_ble(profile, value):
    raw = bytes(value)
    if not raw or len(raw) > 512:
        raise ValueError('Data Bluetooth kosong atau terlalu besar')
    if profile == 'battery':
        if len(raw) != 1 or raw[0] > 100:
            raise ValueError('Level baterai invalid')
        return {'value':raw[0], 'unit':'percent'}
    if profile == 'raw':
        return {'raw_hex':raw.hex()}
    raise ValueError('Unknown Bluetooth profile')


async def read_ble_once(config):
    from bleak import BleakClient
    async with BleakClient(config['ble_address'], timeout=15) as client:
        raw = await client.read_gatt_char(config['ble_characteristic'])
    return {'characteristic':config['ble_characteristic'], **decode_ble(config['ble_profile'], raw)}


def run_ble(config):
    while True:
        if not source_is_active(config):
            time.sleep(min(config['interval_seconds'], 60))
            continue
        try:
            result = asyncio.run(read_ble_once(config))
            send_event(config, 'ble.reading', result)
            print(f'ble {config["source_id"]}: sent', flush=True)
        except Exception:
            # Never log device credentials or raw payloads from a Bluetooth stack.
            print(f'ble {config["source_id"]}: read or send failed', flush=True)
        time.sleep(config['interval_seconds'])


def main():
    config = load_config(os.getenv('GATEWAY_CONFIG', '/config/config.json'))
    workers = {'camera':run_camera,'mqtt':run_mqtt,'home_assistant':run_home_assistant,'http_json':run_http_json,'custom':lambda _: threading.Event().wait(),'ble':run_ble}
    for source in config['sources']:
        worker_config = {**source,'server_url':config['server_url']}
        thread = threading.Thread(target=workers[source['type']], args=(worker_config,), daemon=False)
        thread.start()
    print(f'Gateway started with {len(config["sources"])} sources.', flush=True)


if __name__ == '__main__':
    main()
