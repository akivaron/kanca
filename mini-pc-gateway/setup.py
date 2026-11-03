#!/usr/bin/env python3
"""Interactive setup for multiple sources; never collects a Baseten key."""
import getpass
import json
import os
import re
import uuid
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from detect import main as detect_hardware


class BlockRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def discover_home_assistant(base, token, opener=None):
    """List entities already exposed by a trusted Home Assistant hub."""
    opener = opener or urllib.request.build_opener(BlockRedirect())
    request = urllib.request.Request(base.rstrip('/') + '/api/states', headers={'Authorization':'Bearer '+token, 'Accept':'application/json'})
    with opener.open(request, timeout=10) as response:
        payload = response.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        raise ValueError('Device list is too large')
    items = json.loads(payload)
    if not isinstance(items, list):
        raise ValueError('Response hub invalid')
    result = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('entity_id'), str):
            continue
        entity = item['entity_id']
        if len(entity) > 200 or not all(c.isascii() and (c.isalnum() or c in '._') for c in entity):
            continue
        attributes = item.get('attributes') if isinstance(item.get('attributes'), dict) else {}
        label = attributes.get('friendly_name')
        if not isinstance(label, str): label = entity
        label = ''.join(c for c in label if c.isprintable())[:80]
        result.append({'entity_id':entity,'name':label})
    return sorted(result, key=lambda item: item['entity_id'])[:200]


def choose_entity(base, token):
    try:
        entities = discover_home_assistant(base, token)
    except (OSError, ValueError, UnicodeDecodeError, urllib.error.URLError):
        entities = []
        print('Could not find hub entities. Check the connection or enter an ID manually.')
    if entities:
        print('Devices/entities available in Home Assistant:')
        for index, entity in enumerate(entities, 1):
            print(f"{index}. {entity['name']} ({entity['entity_id']})")
        choice = input('Entity number, or press Enter to enter an ID manually: ').strip()
        if choice:
            try:
                index = int(choice)
                if 1 <= index <= len(entities):
                    return entities[index - 1]['entity_id']
            except ValueError:
                pass
            raise SystemExit('Number entity invalid.')
    return input('ID satu entity Home Assistant: ').strip()


def interval_prompt():
    try:
        value = int(input('Interval in seconds [60]: ').strip() or '60')
        if not 10 <= value <= 86400:
            raise ValueError()
        return value
    except ValueError:
        raise SystemExit('Interval must be between 10 and 86400 seconds.')


def choose_ble_address():
    """Offer an explicit local scan; fall back to manual selection if unavailable."""
    if input('Scan for nearby Bluetooth devices now? [Y/n]: ').strip().lower() not in ('n', 'no'):
        try:
            result = subprocess.run(['docker','compose','-f','compose.ble-scan.yaml','run','--rm','scanner'], capture_output=True, text=True, timeout=60, check=True)
            devices = []
            for line in result.stdout.splitlines():
                parts = line.split(None, 1)
                if parts and re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', parts[0]):
                    devices.append((parts[0].upper(), parts[1] if len(parts)>1 else 'Tanpa nama'))
            if devices:
                for index, (address, name) in enumerate(devices, 1):
                    print(f'{index}. {name} ({address})')
                choice = input('Choose a device number, or press Enter to enter an address manually: ').strip()
                if choice:
                    try:
                        index = int(choice)
                        if 1 <= index <= len(devices): return devices[index-1][0]
                    except ValueError:
                        pass
                    raise SystemExit('Invalid device number.')
            else:
                print('No Bluetooth devices found.')
        except (OSError, subprocess.SubprocessError):
            print('Scanning is unavailable; enter the address manually.')
    return input('Device Bluetooth address (contoh AA:BB:CC:DD:EE:FF): ').strip().upper()


def main():
    path = Path(__file__).resolve().parent / 'config.json'
    if path.exists():
        raise SystemExit('config.json already exists. Back it up or remove it manually to run setup again.')
    detect_hardware()
    base = input('URL server Kanca (HTTPS): ').strip().rstrip('/')
    parsed = urlparse(base)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1'))):
        raise SystemExit('Use an HTTPS URL without credentials; HTTP is allowed only for localhost.')
    sources = []
    while True:
        choice = input('Source type: [1] kamera RTSP, [2] MQTT, [3] Home Assistant, [4] HTTP JSON, [5] adapter kustom, [6] Bluetooth LE, [q] selesai: ').strip().lower()
        if choice == 'q':
            if not sources:
                print('Add at least one source.')
                continue
            break
        if choice not in ('1', '2', '3', '4', '5', '6'):
            print('Unknown selection.')
            continue
        source = {'type': {'1':'camera','2':'mqtt','3':'home_assistant','4':'http_json','5':'custom','6':'ble'}[choice], 'source_id':input('ID sources Kanca: ').strip(), 'source_token':getpass.getpass('Token sources Kanca: ').strip()}
        if not source['source_id'] or not source['source_token']:
            raise SystemExit('Source ID and token are required.')
        source['name'] = input('Device name for gateway logs (optional): ').strip()
        if not source['name']:
            source.pop('name')
        if any(item['source_id'] == source['source_id'] for item in sources):
            raise SystemExit('Use a different Kanca source for each connection.')
        if choice == '1':
            source['camera_url'] = getpass.getpass('URL kamera RTSP atau HLS publik (input tersembunyi): ').strip()
            parsed_camera = urlparse(source['camera_url'])
            rtsp_camera = parsed_camera.scheme in ('rtsp','rtsps') and bool(parsed_camera.hostname)
            public_hls_camera = parsed_camera.scheme == 'https' and parsed_camera.hostname == 'dki-jkt.balitower.co.id' and parsed_camera.path.endswith('/index.fmp4.m3u8') and not parsed_camera.username and not parsed_camera.password and not parsed_camera.query and not parsed_camera.fragment
            if not (rtsp_camera or public_hls_camera):
                raise SystemExit('Use an RTSP/rtsps URL or a supported public DKI Jakarta HLS feed.')
            source['interval_seconds'] = interval_prompt()
            source['audio_enabled'] = input('Send audio from the camera? Only with appropriate permission [y/N]: ').strip().lower() == 'y'
        elif choice == '2':
            source['mqtt_host'] = input('Hostname broker MQTT: ').strip()
            try:
                source['mqtt_port'] = int(input('Port MQTT TLS [8883]: ').strip() or '8883')
                if not 1 <= source['mqtt_port'] <= 65535: raise ValueError()
            except ValueError:
                raise SystemExit('Port MQTT invalid.')
            source['mqtt_topic'] = input('Satu topic MQTT tanpa wildcard: ').strip()
            source['mqtt_username'] = input('Username MQTT (kosong jika none): ').strip()
            source['mqtt_password'] = getpass.getpass('Password MQTT (kosong jika none): ') if source['mqtt_username'] else ''
            if not source['mqtt_host'] or not source['mqtt_topic'] or any(c in source['mqtt_topic'] for c in '#+'):
                raise SystemExit('Hostname dan topic tanpa wildcard wajib diisi.')
        elif choice == '3':
            source['ha_url'] = input('URL Home Assistant: ').strip().rstrip('/')
            source['ha_token'] = getpass.getpass('Token Home Assistant: ').strip()
            url = urlparse(source['ha_url'])
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment or not source['ha_token']:
                raise SystemExit('Home Assistant URL and token must be valid.')
            source['ha_entity'] = choose_entity(source['ha_url'], source['ha_token'])
            source['interval_seconds'] = interval_prompt()
            if not source['ha_entity']:
                raise SystemExit('Home Assistant entity ID is required.')
        elif choice == '4':
            source['http_url'] = getpass.getpass('URL endpoint HTTP JSON (input tersembunyi): ').strip()
            source['http_token'] = getpass.getpass('Bearer token endpoint (kosong jika none): ').strip()
            source['interval_seconds'] = interval_prompt()
            url = urlparse(source['http_url'])
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.fragment or (source['http_token'] and url.scheme != 'https'):
                raise SystemExit('Invalid URL; endpoints using a bearer token must use HTTPS.')
        elif choice == '6':
            source['ble_address'] = choose_ble_address()
            if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', source['ble_address']):
                raise SystemExit('Linux Bluetooth address must be a valid MAC address.')
            profile = input('Data: [1] level baterai standar, [2] characteristic mentah [1]: ').strip() or '1'
            if profile not in ('1', '2'):
                raise SystemExit('Selection data Bluetooth invalid.')
            source['ble_profile'] = 'battery' if profile == '1' else 'raw'
            characteristic = '00002a19-0000-1000-8000-00805f9b34fb' if profile == '1' else input('UUID characteristic 128-bit: ').strip()
            try:
                source['ble_characteristic'] = str(uuid.UUID(characteristic))
            except ValueError:
                raise SystemExit('UUID characteristic invalid.')
            source['interval_seconds'] = interval_prompt()
        sources.append(source)
        print('Source added. For another connection, use a different Kanca source ID and token.')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump({'server_url':base,'sources':sources}, file, indent=2)
    print('Configuration saved. For cameras, enable media analysis in Kanca before starting the gateway.')


if __name__ == '__main__':
    main()
