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
        raise ValueError('Daftar perangkat terlalu besar')
    items = json.loads(payload)
    if not isinstance(items, list):
        raise ValueError('Respons hub tidak valid')
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
        print('Tidak dapat menemukan entity hub. Periksa koneksi atau masukkan ID secara manual.')
    if entities:
        print('Perangkat/entity yang sudah tersedia di Home Assistant:')
        for index, entity in enumerate(entities, 1):
            print(f"{index}. {entity['name']} ({entity['entity_id']})")
        choice = input('Nomor entity, atau tekan Enter untuk memasukkan ID manual: ').strip()
        if choice:
            try:
                index = int(choice)
                if 1 <= index <= len(entities):
                    return entities[index - 1]['entity_id']
            except ValueError:
                pass
            raise SystemExit('Nomor entity tidak valid.')
    return input('ID satu entity Home Assistant: ').strip()


def interval_prompt():
    try:
        value = int(input('Interval dalam detik [60]: ').strip() or '60')
        if not 10 <= value <= 86400:
            raise ValueError()
        return value
    except ValueError:
        raise SystemExit('Interval harus antara 10 dan 86400 detik.')


def choose_ble_address():
    """Offer an explicit local scan; fall back to manual selection if unavailable."""
    if input('Cari perangkat Bluetooth di sekitar sekarang? [Y/n]: ').strip().lower() not in ('n', 'no'):
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
                choice = input('Pilih nomor perangkat, atau Enter untuk memasukkan alamat manual: ').strip()
                if choice:
                    try:
                        index = int(choice)
                        if 1 <= index <= len(devices): return devices[index-1][0]
                    except ValueError:
                        pass
                    raise SystemExit('Nomor perangkat tidak valid.')
            else:
                print('Tidak ada perangkat Bluetooth ditemukan.')
        except (OSError, subprocess.SubprocessError):
            print('Pemindaian tidak tersedia; masukkan alamat secara manual.')
    return input('Alamat Bluetooth perangkat (contoh AA:BB:CC:DD:EE:FF): ').strip().upper()


def main():
    path = Path(__file__).resolve().parent / 'config.json'
    if path.exists():
        raise SystemExit('config.json sudah ada. Cadangkan atau hapus secara manual jika ingin setup ulang.')
    detect_hardware()
    base = input('URL server Kanca (HTTPS): ').strip().rstrip('/')
    parsed = urlparse(base)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1'))):
        raise SystemExit('Gunakan URL HTTPS tanpa kredensial; HTTP hanya untuk localhost.')
    sources = []
    while True:
        choice = input('Jenis sumber: [1] kamera RTSP, [2] MQTT, [3] Home Assistant, [4] HTTP JSON, [5] adapter kustom, [6] Bluetooth LE, [q] selesai: ').strip().lower()
        if choice == 'q':
            if not sources:
                print('Tambahkan sedikitnya satu sumber.')
                continue
            break
        if choice not in ('1', '2', '3', '4', '5', '6'):
            print('Pilihan tidak dikenal.')
            continue
        source = {'type': {'1':'camera','2':'mqtt','3':'home_assistant','4':'http_json','5':'custom','6':'ble'}[choice], 'source_id':input('ID sumber Kanca: ').strip(), 'source_token':getpass.getpass('Token sumber Kanca: ').strip()}
        if not source['source_id'] or not source['source_token']:
            raise SystemExit('ID dan token sumber wajib diisi.')
        if any(item['source_id'] == source['source_id'] for item in sources):
            raise SystemExit('Gunakan sumber Kanca yang berbeda untuk tiap koneksi.')
        if choice == '1':
            source['camera_url'] = getpass.getpass('URL RTSP kamera (input tersembunyi): ').strip()
            if not source['camera_url'].startswith(('rtsp://','rtsps://')):
                raise SystemExit('Gunakan URL RTSP/rtsps yang valid.')
            source['interval_seconds'] = interval_prompt()
            source['audio_enabled'] = input('Kirim audio dari kamera? Hanya dengan izin yang sesuai [y/N]: ').strip().lower() == 'y'
        elif choice == '2':
            source['mqtt_host'] = input('Hostname broker MQTT: ').strip()
            try:
                source['mqtt_port'] = int(input('Port MQTT TLS [8883]: ').strip() or '8883')
                if not 1 <= source['mqtt_port'] <= 65535: raise ValueError()
            except ValueError:
                raise SystemExit('Port MQTT tidak valid.')
            source['mqtt_topic'] = input('Satu topic MQTT tanpa wildcard: ').strip()
            source['mqtt_username'] = input('Username MQTT (kosong jika tidak ada): ').strip()
            source['mqtt_password'] = getpass.getpass('Password MQTT (kosong jika tidak ada): ') if source['mqtt_username'] else ''
            if not source['mqtt_host'] or not source['mqtt_topic'] or any(c in source['mqtt_topic'] for c in '#+'):
                raise SystemExit('Hostname dan topic tanpa wildcard wajib diisi.')
        elif choice == '3':
            source['ha_url'] = input('URL Home Assistant: ').strip().rstrip('/')
            source['ha_token'] = getpass.getpass('Token Home Assistant: ').strip()
            url = urlparse(source['ha_url'])
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment or not source['ha_token']:
                raise SystemExit('URL dan token Home Assistant harus valid.')
            source['ha_entity'] = choose_entity(source['ha_url'], source['ha_token'])
            source['interval_seconds'] = interval_prompt()
            if not source['ha_entity']:
                raise SystemExit('ID entity Home Assistant harus diisi.')
        elif choice == '4':
            source['http_url'] = getpass.getpass('URL endpoint HTTP JSON (input tersembunyi): ').strip()
            source['http_token'] = getpass.getpass('Bearer token endpoint (kosong jika tidak ada): ').strip()
            source['interval_seconds'] = interval_prompt()
            url = urlparse(source['http_url'])
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.fragment or (source['http_token'] and url.scheme != 'https'):
                raise SystemExit('URL tidak valid; endpoint dengan bearer token harus menggunakan HTTPS.')
        elif choice == '6':
            source['ble_address'] = choose_ble_address()
            if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', source['ble_address']):
                raise SystemExit('Alamat Bluetooth Linux harus berupa MAC yang valid.')
            profile = input('Data: [1] level baterai standar, [2] characteristic mentah [1]: ').strip() or '1'
            if profile not in ('1', '2'):
                raise SystemExit('Pilihan data Bluetooth tidak valid.')
            source['ble_profile'] = 'battery' if profile == '1' else 'raw'
            characteristic = '00002a19-0000-1000-8000-00805f9b34fb' if profile == '1' else input('UUID characteristic 128-bit: ').strip()
            try:
                source['ble_characteristic'] = str(uuid.UUID(characteristic))
            except ValueError:
                raise SystemExit('UUID characteristic tidak valid.')
            source['interval_seconds'] = interval_prompt()
        sources.append(source)
        print('Sumber ditambahkan. Untuk koneksi lain, gunakan ID dan token sumber Kanca yang berbeda.')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump({'server_url':base,'sources':sources}, file, indent=2)
    print('Konfigurasi disimpan. Untuk kamera, aktifkan analisis media di Kanca sebelum menjalankan gateway.')


if __name__ == '__main__':
    main()
