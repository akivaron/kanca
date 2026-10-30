"""Example external consumer. Persist seen IDs in a real integration."""
import os
import time
import httpx

base = os.getenv("KANCA_URL", "http://localhost:8765")
key = os.environ["KANCA_API_KEY"]
cursor = 0
while True:
    response = httpx.get(f"{base}/v1/events", headers={"X-API-Key": key}, params={"after": cursor}, timeout=10)
    response.raise_for_status()
    for event in response.json():
        print(event, flush=True)
        cursor = event["cursor"]
    time.sleep(2)
