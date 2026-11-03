"""Poll selected Home Assistant entities and send state events to Kanca."""
import os
import time
import math
import httpx
from common import emit


def normalize_state(entity, state):
    raw = state['state']
    if not isinstance(raw, str) or raw in ('unknown', 'unavailable'):
        raise ValueError('State unavailable')
    result = {'entity_id': entity, 'state': raw, 'unit': state.get('attributes', {}).get('unit_of_measurement'), 'last_updated': state.get('last_updated')}
    try:
        value = float(raw)
        if math.isfinite(value):
            result['value'] = value
    except ValueError:
        pass
    return result


def main():
    base = os.environ['HA_URL'].rstrip('/')
    token = os.environ['HA_TOKEN']
    entities = [item.strip() for item in os.environ['HA_ENTITIES'].split(',') if item.strip()]
    interval = max(5, int(os.getenv('GATEWAY_INTERVAL', '30')))
    if len(entities) != 1:
        raise SystemExit('Use exactly one entity per Kanca source to avoid mixing data between devices')
    while True:
        for entity in entities:
            try:
                response = httpx.get(f'{base}/api/states/{entity}', headers={'Authorization': f'Bearer {token}'}, timeout=10)
                response.raise_for_status()
                state = response.json()
                emit('home_assistant.state', normalize_state(entity, state))
            except (httpx.HTTPError, KeyError, ValueError):
                print(f'Failed membaca atau meneruskan entity {entity}', flush=True)
        time.sleep(interval)


if __name__ == '__main__':
    main()
