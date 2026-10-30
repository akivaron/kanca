"""Forward newline-delimited JSON objects from a custom local adapter to Kanca."""
import json
import os
import sys
from gateway import load_config, send_event


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Gunakan: adapter_example.py SOURCE_ID')
    config = load_config(os.getenv('GATEWAY_CONFIG', '/config/config.json'))
    source = next((item for item in config['sources'] if item['source_id'] == sys.argv[1] and item['type'] == 'custom'), None)
    if source is None:
        raise SystemExit('Sumber adapter kustom tidak ditemukan')
    target = {**source, 'server_url':config['server_url']}
    while line := sys.stdin.buffer.readline(24001):
        try:
            if len(line) > 24000:
                while line and not line.endswith(b'\n'):
                    line = sys.stdin.buffer.readline(24001)
                raise ValueError('Terlalu besar')
            value = json.loads(line)
            if not isinstance(value, dict): raise ValueError('Harus objek JSON')
            send_event(target, 'custom.data', {'payload':value})
            print('terkirim', file=sys.stderr, flush=True)
        except (ValueError, UnicodeDecodeError, OSError):
            print('event tidak valid atau gagal dikirim', file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
