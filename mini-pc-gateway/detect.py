"""Read-only local inventory; candidates are hints, not compatibility guarantees."""
import json
import platform
import re
import subprocess
from pathlib import Path


def read_text(path):
    try:
        return path.read_text(errors='replace').strip()[:160]
    except OSError:
        return ''


def detect(sys_usb=Path('/sys/bus/usb/devices'), serial_root=Path('/dev/serial/by-id')):
    devices = []
    try:
        nodes = list(sys_usb.iterdir())
    except OSError:
        nodes = []
    for node in nodes:
        vendor, product = read_text(node/'idVendor'), read_text(node/'idProduct')
        if not re.fullmatch(r'[0-9a-fA-F]{4}', vendor) or not re.fullmatch(r'[0-9a-fA-F]{4}', product):
            continue
        manufacturer = ''.join(c for c in read_text(node/'manufacturer') if c.isprintable())
        name = ''.join(c for c in read_text(node/'product') if c.isprintable())
        label = (manufacturer + ' ' + name).lower()
        candidates = []
        if 'zigbee' in label: candidates.append('Zigbee')
        if 'zwave' in label or 'z-wave' in label: candidates.append('Z-Wave')
        if 'thread' in label: candidates.append('Thread')
        if 'bluetooth' in label or read_text(node/'bDeviceClass').lower() == 'e0': candidates.append('Bluetooth')
        devices.append({'vendor_id':vendor.lower(),'product_id':product.lower(),'manufacturer':manufacturer,'product':name,'protocol_candidates':candidates})
    try:
        serial = sorted(str(path) for path in serial_root.iterdir())
    except OSError:
        serial = []
    try:
        result = subprocess.run(['bluetoothctl','show'], capture_output=True, text=True, timeout=5, check=False)
        bluetooth = 'available' if result.returncode == 0 and 'Controller ' in result.stdout else 'unavailable_or_unknown'
    except (OSError, subprocess.TimeoutExpired):
        bluetooth = 'unavailable_or_unknown'
    return {'os':platform.system(), 'architecture':platform.machine(), 'usb_devices':devices, 'serial_devices':serial, 'bluetooth_controller':bluetooth}


def main():
    result = detect()
    print('OS:', result['os'], '· arsitektur:', result['architecture'])
    print('Bluetooth controller:', 'detected' if result['bluetooth_controller']=='available' else 'cannot be confirmed')
    if not result['usb_devices']:
        print('USB radio could not be identified automatically.')
    for device in result['usb_devices']:
        label = ' '.join(x for x in (device['manufacturer'],device['product']) if x) or 'Name unavailable'
        hints = ', '.join(device['protocol_candidates']) or 'protocol unknown'
        print(f"USB {device['vendor_id']}:{device['product_id']} · {label} · kandidat: {hints}")
    for path in result['serial_devices']:
        print('Port serial:', path)
    print('Candidate results do not confirm compatibility, pairing, or driver support.')


if __name__ == '__main__':
    main()
