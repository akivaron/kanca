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


def load_config(path):
    config = json.loads(Path(path).read_text())
    parsed = urllib.parse.urlparse(config.get('server_url', ''))
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1', 'host.docker.internal'))):
        raise ValueError('URL Kanca harus HTTPS, kecuali localhost untuk pengujian')
    if 'sources' not in config:
        config['sources'] = [{**{k:v for k,v in config.items() if k != 'server_url'}, 'type':'camera'}]
    sources = config['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= 32:
        raise ValueError('Konfigurasi harus memiliki 1–32 sumber')
    ids = set()
    for source in sources:
        if not isinstance(source, dict) or not source.get('source_id') or not source.get('source_token') or source['source_id'] in ids:
            raise ValueError('ID dan token sumber wajib unik')
        if 'name' in source and (not isinstance(source['name'], str) or not 1 <= len(source['name'].strip()) <= 100):
            raise ValueError('Nama sumber tidak valid')
        ids.add(source['source_id'])
        kind = source.get('type')
        if kind in ('camera', 'home_assistant', 'http_json', 'ble') and (type(source.get('interval_seconds')) is not int or not 10 <= source['interval_seconds'] <= 86400):
            raise ValueError('Interval tidak valid')
        if kind == 'camera':
            camera_url = urllib.parse.urlparse(str(source.get('camera_url', '')))
            rtsp_camera = camera_url.scheme in ('rtsp', 'rtsps') and bool(camera_url.hostname)
            public_hls_camera = camera_url.scheme == 'https' and camera_url.hostname == 'dki-jkt.balitower.co.id' and camera_url.path.endswith('/index.fmp4.m3u8') and not camera_url.username and not camera_url.password and not camera_url.query and not camera_url.fragment
            if not (rtsp_camera or public_hls_camera) or type(source.get('audio_enabled', False)) is not bool:
                raise ValueError('Konfigurasi kamera tidak valid')
        elif kind == 'mqtt':
            if not source.get('mqtt_host') or not source.get('mqtt_topic') or any(c in source['mqtt_topic'] for c in '#+') or type(source.get('mqtt_port', 8883)) is not int or not 1 <= source.get('mqtt_port', 8883) <= 65535:
                raise ValueError('Konfigurasi MQTT tidak valid')
        elif kind == 'home_assistant':
            url = urllib.parse.urlparse(source.get('ha_url', ''))
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment or not source.get('ha_token') or not source.get('ha_entity'):
                raise ValueError('Konfigurasi Home Assistant tidak valid')
        elif kind == 'http_json':
            url = urllib.parse.urlparse(source.get('http_url', ''))
            event_type = source.get('event_type', 'http.json')
            if not isinstance(event_type, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', event_type) or url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.fragment or (source.get('http_token') and url.scheme != 'https'):
                raise ValueError('Konfigurasi HTTP JSON tidak valid; bearer token memerlukan HTTPS')
        elif kind == 'custom':
            pass
        elif kind == 'ble':
            address = source.get('ble_address')
            if not isinstance(address, str) or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', address) or source.get('ble_profile') not in ('raw','battery'):
                raise ValueError('Konfigurasi Bluetooth tidak valid')
            try:
                characteristic = uuid.UUID(source.get('ble_characteristic', ''))
            except (ValueError, AttributeError, TypeError) as exc:
                raise ValueError('UUID Bluetooth tidak valid') from exc
            if source['ble_profile'] == 'battery' and str(characteristic) != '00002a19-0000-1000-8000-00805f9b34fb':
                raise ValueError('Profil baterai memerlukan characteristic baterai standar')
        else:
            raise ValueError('Jenis sumber tidak didukung')
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


def normalize_ha(entity, state):
    raw = state['state']
    if not isinstance(raw, str) or raw in ('unknown', 'unavailable'):
        raise ValueError('State tidak tersedia')
    result = {'entity_id':entity, 'state':raw, 'unit':state.get('attributes', {}).get('unit_of_measurement'), 'last_updated':state.get('last_updated')}
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
        raise ValueError('Payload harus objek')
    return {'topic':message.topic, 'payload':payload}


def run_camera(config):
    while True:
        for kind in (['vision', 'audio'] if config.get('audio_enabled') else ['vision']):
            try:
                send(config, kind, capture(config, kind))
                print(f'camera {source_label(config)}: {kind} terkirim', flush=True)
            except (OSError, ValueError, subprocess.SubprocessError, urllib.error.URLError) as exc:
                status = getattr(exc, 'code', None)
                print(f'camera {source_label(config)}: {kind} gagal' + (f' (HTTP {status})' if status else ''), flush=True)
        time.sleep(config['interval_seconds'])


def run_home_assistant(config):
    entity = config['ha_entity']
    url = config['ha_url'].rstrip('/') + '/api/states/' + urllib.parse.quote(entity, safe='.')
    while True:
        try:
            request = urllib.request.Request(url, headers={'Authorization':'Bearer '+config['ha_token']})
            with no_redirect.open(request, timeout=10) as response:
                raw = response.read(65537)
            if len(raw) > 65536: raise ValueError('Respons terlalu besar')
            send_event(config, 'home_assistant.state', normalize_ha(entity, json.loads(raw)))
            print(f'home_assistant {source_label(config)}: terkirim', flush=True)
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
            print(f'home_assistant {source_label(config)}: gagal membaca atau mengirim', flush=True)
        time.sleep(config['interval_seconds'])


def read_http_json(config):
    headers = {'Accept':'application/json', 'User-Agent':'KancaGateway/1.0 (+https://bmkg.go.id)'}
    if config.get('http_token'):
        headers['Authorization'] = 'Bearer ' + config['http_token']
    request = urllib.request.Request(config['http_url'], headers=headers)
    with no_redirect.open(request, timeout=10) as response:
        raw = response.read(24001)
    if len(raw) > 24000:
        raise ValueError('Respons HTTP terlalu besar')
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Respons HTTP harus berupa objek JSON')
    return data


def run_http_json(config):
    while True:
        try:
            send_event(config, config.get('event_type', 'http.json'), {'payload': read_http_json(config)})
            print(f'http_json {config["source_id"]}: terkirim', flush=True)
        except (OSError, ValueError, UnicodeDecodeError, urllib.error.URLError):
            print(f'http_json {config["source_id"]}: gagal membaca atau mengirim', flush=True)
        time.sleep(config['interval_seconds'])


def run_mqtt(config):
    import paho.mqtt.client as mqtt
    while True:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            if config.get('mqtt_username'):
                client.username_pw_set(config['mqtt_username'], config.get('mqtt_password', ''))
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            def on_connect(client, userdata, flags, reason_code, properties):
                if reason_code.is_failure:
                    print(f'mqtt {config["source_id"]}: koneksi ditolak', flush=True)
                else:
                    client.subscribe(config['mqtt_topic'], qos=1)
            def on_message(client, userdata, message):
                try:
                    data = mqtt_payload(message)
                    if data is None:
                        print(f'mqtt {config["source_id"]}: pesan retained dilewati', flush=True)
                        return
                    send_event(config, 'mqtt.message', data)
                except (ValueError, UnicodeDecodeError, OSError, urllib.error.URLError):
                    print(f'mqtt {config["source_id"]}: pesan tidak valid atau gagal dikirim', flush=True)
            client.on_connect, client.on_message = on_connect, on_message
            client.connect(config['mqtt_host'], config.get('mqtt_port', 8883), 60)
            client.loop_forever(retry_first_connection=True)
        except (OSError, ValueError):
            print(f'mqtt {config["source_id"]}: koneksi gagal; mencoba lagi', flush=True)
        time.sleep(10)


def decode_ble(profile, value):
    raw = bytes(value)
    if not raw or len(raw) > 512:
        raise ValueError('Data Bluetooth kosong atau terlalu besar')
    if profile == 'battery':
        if len(raw) != 1 or raw[0] > 100:
            raise ValueError('Level baterai tidak valid')
        return {'value':raw[0], 'unit':'percent'}
    if profile == 'raw':
        return {'raw_hex':raw.hex()}
    raise ValueError('Profil Bluetooth tidak dikenal')


async def read_ble_once(config):
    from bleak import BleakClient
    async with BleakClient(config['ble_address'], timeout=15) as client:
        raw = await client.read_gatt_char(config['ble_characteristic'])
    return {'characteristic':config['ble_characteristic'], **decode_ble(config['ble_profile'], raw)}


def run_ble(config):
    while True:
        try:
            result = asyncio.run(read_ble_once(config))
            send_event(config, 'ble.reading', result)
            print(f'ble {config["source_id"]}: terkirim', flush=True)
        except Exception:
            # Never log device credentials or raw payloads from a Bluetooth stack.
            print(f'ble {config["source_id"]}: pembacaan atau pengiriman gagal', flush=True)
        time.sleep(config['interval_seconds'])


def main():
    config = load_config(os.getenv('GATEWAY_CONFIG', '/config/config.json'))
    workers = {'camera':run_camera,'mqtt':run_mqtt,'home_assistant':run_home_assistant,'http_json':run_http_json,'custom':lambda _: threading.Event().wait(),'ble':run_ble}
    for source in config['sources']:
        thread = threading.Thread(target=workers[source['type']], args=({**source,'server_url':config['server_url']},), daemon=False)
        thread.start()
    print(f'Gateway dimulai dengan {len(config["sources"])} sumber.', flush=True)


if __name__ == '__main__':
    main()
