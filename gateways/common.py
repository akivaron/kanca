"""Shared ingestion client; credentials come from environment, never from logs."""
import os
import httpx


def emit(kind, data):
    base = os.environ['KANCA_URL'].rstrip('/')
    source = os.environ['KANCA_SOURCE_ID']
    token = os.environ['KANCA_SOURCE_TOKEN']
    response = httpx.post(f'{base}/v1/ingest/{source}', headers={'Authorization': f'Bearer {token}'}, json={'type': kind, 'data': data}, timeout=10)
    response.raise_for_status()
