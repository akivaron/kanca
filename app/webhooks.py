"""Signed, at-least-once webhook delivery with address pinning."""
import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from app.storage import connect, event_dict, now


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError("Webhook must be URL HTTPS publik pada port 443 tanpa kredensial atau fragment.")
    return parsed


def public_ip(host):
    addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Webhook address must use a public IP address.")
    return sorted(addresses)[0]


def post_pinned(url, payload, headers):
    parsed = validate_url(url)
    ip = public_ip(parsed.hostname)
    raw = socket.create_connection((ip, 443), timeout=5)
    try:
        tls = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
        conn = http.client.HTTPSConnection(parsed.hostname, timeout=5)
        conn.sock = tls
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        conn.request("POST", path, body=payload, headers=headers)
        response = conn.getresponse()
        status = response.status
        conn.close()
        return status
    finally:
        raw.close()


def deliver_one():
    db = connect()
    try:
        # A lease lets another worker retry after a crash; delivery is at-least-once.
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE deliveries SET status='failed' WHERE status='sending' AND attempts>=5 AND next_attempt<=?", (now(),))
        query = "SELECT d.*,s.url,s.secret,e.tenant,e.task_id,e.type,e.occurred_at,e.data FROM deliveries d JOIN subscriptions s ON s.id=d.subscription_id JOIN events e ON e.id=d.event_id WHERE s.active=1 AND d.status IN ('pending','sending') AND d.next_attempt<=? ORDER BY d.next_attempt LIMIT 1"
        if getattr(db, 'is_postgres', False): query += " FOR UPDATE OF d SKIP LOCKED"
        row = db.execute(query, (now(),)).fetchone()
        if row is None:
            db.commit()
            return False
        lease = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
        db.execute("UPDATE deliveries SET status='sending',attempts=attempts+1,next_attempt=? WHERE id=?", (lease, row["id"]))
        db.commit()
        envelope = {"id": row["event_id"], "tenant_id": row["tenant"], "task_id": row["task_id"], "type": row["type"], "occurred_at": row["occurred_at"], "data": json.loads(row["data"])}
        payload = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        signature = hmac.new(row["secret"].encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
        status = None
        try:
            status = post_pinned(row["url"], payload, {"Content-Type": "application/json", "X-Kanca-Timestamp": timestamp, "X-Kanca-Signature": "sha256=" + signature})
        except (OSError, ValueError, ssl.SSLError, http.client.HTTPException):
            pass
        attempts = row["attempts"] + 1
        delivered = status is not None and 200 <= status < 300
        next_attempt = (datetime.now(timezone.utc) + timedelta(seconds=min(3600, 2 ** attempts))).isoformat()
        with db:
            db.execute("UPDATE deliveries SET status=?,next_attempt=?,last_status=? WHERE id=? AND status='sending' AND attempts=?", ("delivered" if delivered else ("failed" if attempts >= 5 else "pending"), next_attempt, status, row["id"], attempts))
        return True
    finally:
        db.close()
