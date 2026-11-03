"""Explicit local BLE discovery; discovered devices are not paired or uploaded."""
import asyncio
from bleak import BleakScanner


async def main():
    devices = await BleakScanner.discover(timeout=6.0)
    if not devices:
        print('No devices found.')
    for device in devices:
        name = ''.join(c for c in (device.name or 'Tanpa nama') if c.isprintable())[:80]
        print(f'{device.address}  {name}')


if __name__ == '__main__':
    asyncio.run(main())
