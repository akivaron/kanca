"""Verify raw webhook body; persist processed event IDs separately for deduplication."""
import hashlib
import hmac
import time


def verify(secret: str, timestamp: str, signature: str, body: bytes, max_age_seconds: int = 300) -> bool:
    try:
        sent_at = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - sent_at) > max_age_seconds:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
