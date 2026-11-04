import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import asyncio
import csv
import io
import threading
import time
import urllib.parse
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.connectors.registry import CAPABILITIES, describe
from app.connectors.odoo import OdooClient, OdooError, validate_base_url
from app.connectors import erp_demo
from app.credentials import encrypt_credentials, decrypt_credentials
from app.planner import PlanningError, answer_source_question, propose, route_source_data_request
from app.service import validate_steps
from app.storage import acquire_task_source_automation, connect, event, event_dict, initialize, now, release_task_source_automation, task_dict, uid
from app.webhooks import validate_url
from app import media

try:
    import psycopg
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
except ImportError:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


@asynccontextmanager
async def lifespan(_app):
    initialize()
    yield


app = FastAPI(title="Kanca Agent Platform", version="0.1.0", lifespan=lifespan)
PUBLIC_BMKG_WEATHER_LOCATIONS = json.loads((Path(__file__).resolve().parent / "public_bmkg_locations.json").read_text())
PUBLIC_BMKG_WEATHER_BY_CODE = {item["code"]: item for item in PUBLIC_BMKG_WEATHER_LOCATIONS}
PUBLIC_CCTV_CATALOG = json.loads((Path(__file__).resolve().parent / "public_cctv_sources.json").read_text())
PUBLIC_CCTV_ADDITIONAL_CATALOG = json.loads((Path(__file__).resolve().parent / "public_cctv_sources_additional.json").read_text())
PUBLIC_CCTV_SOURCES = PUBLIC_CCTV_CATALOG["sources"] + PUBLIC_CCTV_ADDITIONAL_CATALOG["sources"]
PUBLIC_CCTV_BY_ID = {item["catalog_id"]: item for item in PUBLIC_CCTV_SOURCES}
_pending_source_requests: dict[str, str] = {}
_pending_source_requests_lock = threading.Lock()
_in_flight_source_requests: dict[str, tuple[float, str]] = {}
_source_request_waiters: dict[str, dict[str, Any]] = {}
_source_previews: dict[str, dict[str, Any]] = {}
_source_previews_lock = threading.Lock()
_SOURCE_PREVIEW_TTL_SECONDS = 120
_SOURCE_PREVIEW_MAX_BYTES = 32 * 1024 * 1024


def public_cctv_source_name(item: dict[str, Any]) -> str:
    if item["catalog_id"].startswith("pantau-"):
        external_id = item["catalog_id"].removeprefix("pantau-")
        short_id = hashlib.sha256(external_id.encode()).hexdigest()[:10]
        return f"CCTV · {item['name'][:58]} · {item['city'][:12]} · {short_id}"
    label = f"CCTV · {item['name']} · {item['city']} ({item['catalog_id']})"
    return label[:100]


def insert_public_cctv_source(db, tenant: str, item: dict[str, Any]):
    name = public_cctv_source_name(item)
    existing = db.execute(
        "SELECT id FROM sources WHERE tenant=? AND name=? AND status!='deleted'",
        (tenant, name),
    ).fetchone()
    if existing:
        return None
    sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
    db.execute(
        "INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)",
        (sid, tenant, name, "camera", hashlib.sha256(token.encode()).hexdigest(), "disabled", ts, None, 300),
    )
    prompt = "Summarize visible road or public-area conditions. Describe congestion or notable events without identifying people or vehicles. State when the image is unclear."
    db.execute("INSERT INTO source_media_settings VALUES (?,?,?,?,?)", (sid, 0, 0, prompt, "Audio analysis is disabled."))
    return {"id": sid, "name": name, "kind": "camera", "status": "disabled", "created_at": ts, "token": token, "camera_url": item["url"], "public_stream_url": item["url"], "interval_seconds": 300, "vision_enabled": False}

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (FRONTEND_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


def session_token(key: str) -> str:
    return hmac.new(key.encode(), b"kanca-local-ui-session-v1", hashlib.sha256).hexdigest()


def one_shot_request_timestamp(sid: str) -> str | None:
    with _pending_source_requests_lock:
        request = _in_flight_source_requests.get(sid)
        if request is None:
            return None
        if time.monotonic() - request[0] > 120:
            _in_flight_source_requests.pop(sid, None)
            return None
        return request[1]


def one_shot_request_in_flight(sid: str) -> bool:
    return one_shot_request_timestamp(sid) is not None


def notify_source_request(sid: str, requested_at: str | None, outcome: str):
    if not requested_at:
        return
    with _pending_source_requests_lock:
        waiter = _source_request_waiters.get(sid)
        if waiter and waiter['requested_at'] == requested_at:
            waiter['outcome'] = outcome
            waiter['event'].set()


def store_source_preview(sid: str, requested_at: str, raw: bytes, mime: str, status: str):
    now_mono = time.monotonic()
    with _source_previews_lock:
        for key in [key for key, value in _source_previews.items() if value['expires_at'] <= now_mono]:
            _source_previews.pop(key, None)
        _source_previews.pop(sid, None)
        total = sum(len(value['raw']) for value in _source_previews.values())
        while _source_previews and total + len(raw) > _SOURCE_PREVIEW_MAX_BYTES:
            oldest = next(iter(_source_previews))
            removed = _source_previews.pop(oldest)
            total -= len(removed['raw'])
        if len(raw) <= _SOURCE_PREVIEW_MAX_BYTES:
            _source_previews[sid] = {
                'requested_at': requested_at,
                'raw': raw,
                'mime': mime,
                'status': status,
                'expires_at': now_mono + _SOURCE_PREVIEW_TTL_SECONDS,
            }


def update_source_preview_status(sid: str, requested_at: str, status: str):
    with _source_previews_lock:
        preview = _source_previews.get(sid)
        if preview and preview['requested_at'] == requested_at:
            preview['status'] = status


def tenant_auth(request: Request, x_api_key: str = Header(default="")) -> str:
    key = os.getenv("KANCA_API_KEY", "")
    via_header = bool(key and hmac.compare_digest(hashlib.sha256(x_api_key.encode()).digest(), hashlib.sha256(key.encode()).digest()))
    via_cookie = bool(key and hmac.compare_digest(request.cookies.get("kanca_session", ""), session_token(key)))
    if not via_header and not via_cookie:
        raise HTTPException(401, "API key invalid atau not configured")
    if via_cookie and not via_header and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Origin invalid")
    # This initial deployment has exactly one configured tenant.
    return "default"


class ConnectionRequest(BaseModel):
    type: str


class OdooConnectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=8, max_length=500)
    database: str | None = Field(default=None, max_length=100)
    api_key: str = Field(min_length=1, max_length=500)


class PublicBmkgLocationInput(BaseModel):
    adm4_code: str = Field(min_length=13, max_length=13, pattern=r"^\d{2}\.\d{2}\.\d{2}\.\d{4}$")


class PublicCctvInput(BaseModel):
    catalog_id: str = Field(min_length=1, max_length=100)


class Step(BaseModel):
    capability: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    condition: dict[str, Any] | None = None


class Schedule(BaseModel):
    interval_seconds: int = Field(ge=1, le=86400)
    max_runs: int = Field(ge=1, le=1000)


class ScheduleUpdate(BaseModel):
    version: int = Field(ge=1)
    schedule: Schedule


class TaskRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    explicit_steps: list[Step] | None = None
    schedule: Schedule | None = None


class Approval(BaseModel):
    version: int


class SubscriptionRequest(BaseModel):
    url: str = Field(max_length=2048)
    event_types: list[str] = Field(default_factory=lambda: ['*'], max_length=50)


class SubscriptionEventTypes(BaseModel):
    event_types: list[str] = Field(max_length=50)


class ConversationRequest(BaseModel):
    title: str = Field(default="Percakapan baru", min_length=1, max_length=100)


class ConversationUpdate(BaseModel):
    status: str = Field(pattern="^(active|draft)$")


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SourceInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=50)
    expected_interval_seconds: int = Field(default=300, ge=10, le=86400)


class SourceUpdate(SourceInput):
    status: str = Field(pattern="^(active|disabled)$")


class SourceAutomationUpdate(BaseModel):
    enabled: bool
    interval_seconds: int = Field(default=30, ge=5, le=3600)


class DemoGatewayControl(BaseModel):
    enabled: bool


class MediaSettings(BaseModel):
    vision_enabled: bool = False
    audio_enabled: bool = False
    vision_prompt: str = Field(default='Describe the visible operating conditions.', min_length=1, max_length=500)
    audio_prompt: str = Field(default='Summarize the audible sounds.', min_length=1, max_length=500)


class SourceQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class EventTypePreferences(BaseModel):
    event_types: list[str] = Field(max_length=20)


def source_health(source):
    if source['status'] != 'active':
        return {'state': 'disabled', 'stale_after_seconds': None}
    if not source['last_seen']:
        return {'state': 'waiting', 'stale_after_seconds': source['expected_interval_seconds'] * 2}
    try:
        last_seen = datetime.fromisoformat(source['last_seen'])
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        stale_after = source['expected_interval_seconds'] * 2
        age = max(0, (datetime.now(timezone.utc) - last_seen.astimezone(timezone.utc)).total_seconds())
        return {'state': 'delayed' if age > stale_after else 'recent', 'stale_after_seconds': stale_after, 'age_seconds': int(age)}
    except (ValueError, TypeError):
        return {'state': 'unknown', 'stale_after_seconds': source['expected_interval_seconds'] * 2}


media_slots = asyncio.Semaphore(2)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    index = FRONTEND_DIR / "index.html"
    if not index.is_file():
        return JSONResponse({"detail": "Frontend has not been built. Jalankan npm install && npm run build di folder frontend."}, status_code=503)
    return FileResponse(index)


@app.get("/v1/session", include_in_schema=False)
def ui_session():
    response = JSONResponse({"status": "ok"} if os.getenv("KANCA_API_KEY") else {"detail": "KANCA_API_KEY not configured"}, status_code=200 if os.getenv("KANCA_API_KEY") else 503)
    key = os.getenv("KANCA_API_KEY", "")
    if key:
        response.set_cookie("kanca_session", session_token(key), httponly=True, samesite="strict", path="/")
    return response


@app.get("/v1/connector-types")
def connector_types(tenant: str = Depends(tenant_auth)):
    return [{"type": "business_demo", "mode": "simulated"}, {"type": "device_demo", "mode": "simulated"}, {"type": "erp_demo", "mode": "simulated"}]


@app.post("/v1/sources", status_code=201)
def create_source(body: SourceInput, tenant: str = Depends(tenant_auth)):
    name, kind = body.name.strip(), body.kind.strip()
    if not name or not kind:
        raise HTTPException(422, "Source name and type are required")
    sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
    with connect() as db:
        db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, name, kind, hashlib.sha256(token.encode()).hexdigest(), "active", ts, None, body.expected_interval_seconds))
    return {"id": sid, "name": name, "kind": kind, "status": "active", "created_at": ts, "token": token, "ingest_path": f"/v1/ingest/{sid}"}


@app.post("/v1/sources/{sid}/demo-gateway")
def control_demo_gateway(sid: str, body: DemoGatewayControl, tenant: str = Depends(tenant_auth)):
    status = "active" if body.enabled else "paused"
    with connect() as db:
        cur = db.execute("UPDATE sources SET status=? WHERE id=? AND tenant=? AND name='Gateway Penerimaan Gudang Demo' AND kind='iot'", (status, sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Demo warehouse gateway not found")
    return {"id": sid, "status": status, "simulated": True}


@app.post("/v1/sources/simulator-pack", status_code=201)
def create_simulator_source_pack(tenant: str = Depends(tenant_auth)):
    presets = [("Kamera Gudang", "camera"), ("Kamera Area Staf", "camera"), ("Sensor Suhu", "iot")]
    with connect() as db:
        existing = db.execute(
            "SELECT name FROM sources WHERE tenant=? AND status!='deleted' AND name IN (?,?,?)",
            (tenant, *(name for name, _ in presets)),
        ).fetchall()
        if existing:
            names = ", ".join(row["name"] for row in existing)
            raise HTTPException(409, f"Demo sources already exist: {names}. Remove the existing sources before creating a new set.")
        created = []
        for name, kind in presets:
            sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
            db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, name, kind, hashlib.sha256(token.encode()).hexdigest(), "active", ts, None, 300))
            created.append({"id": sid, "name": name, "kind": kind, "status": "active", "created_at": ts, "token": token, "ingest_path": f"/v1/ingest/{sid}"})
    return {"sources": created}


@app.post("/v1/sources/public-cctv-pack", status_code=201)
def create_public_cctv_source_pack(tenant: str = Depends(tenant_auth)):
    presets = [
        ("CCTV Publik Gatot Subroto", "https://dki-jkt.balitower.co.id:7028/502045_JKP_POLDA_JPO-JL.-GATOT-SUBROTO-7_CCTV-01/index.fmp4.m3u8", "https://dki-jkt.balitower.co.id:7028/502045_JKP_POLDA_JPO-JL.-GATOT-SUBROTO-7_CCTV-01/embed.html"),
        ("CCTV Publik Gerbang Pemuda", "https://dki-jkt.balitower.co.id:7028/502160_JKP_POLDA_JL.-GERBANG-PEMUDA-C03_CCTV-01/index.fmp4.m3u8", "https://dki-jkt.balitower.co.id:7028/502160_JKP_POLDA_JL.-GERBANG-PEMUDA-C03_CCTV-01/embed.html"),
    ]
    with connect() as db:
        existing = db.execute(
            "SELECT name FROM sources WHERE tenant=? AND status!='deleted' AND name IN (?,?)",
            (tenant, *(name for name, _, _ in presets)),
        ).fetchall()
        if existing:
            names = ", ".join(row["name"] for row in existing)
            raise HTTPException(409, f"Public CCTV sources already exist: {names}. Remove the existing sources before recreating them.")
        created = []
        for name, camera_url, public_stream_url in presets:
            sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
            db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, name, "camera", hashlib.sha256(token.encode()).hexdigest(), "disabled", ts, None, 120))
            prompt = "Summarize visible traffic conditions. Describe congestion and road conditions without identifying people or vehicles. State when the image is unclear."
            db.execute("INSERT INTO source_media_settings VALUES (?,?,?,?,?)", (sid, 1, 0, prompt, "Audio analysis is disabled."))
            created.append({"id": sid, "name": name, "kind": "camera", "status": "disabled", "created_at": ts, "token": token, "camera_url": camera_url, "public_stream_url": public_stream_url, "interval_seconds": 120, "vision_enabled": True})
    return {"sources": created}


@app.get("/v1/public-sources/cctv")
def list_public_cctv_sources(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        existing = {row["name"] for row in db.execute(
            "SELECT name FROM sources WHERE tenant=? AND status!='deleted'",
            (tenant,),
        ).fetchall()}
    return [{
        "catalog_id": item["catalog_id"],
        "source_name": public_cctv_source_name(item),
        "name": item["name"],
        "city": item["city"],
        "province": item["province"],
        "area": item.get("area"),
        "address": item.get("address"),
        "country": item["country"],
        "provider": urllib.parse.urlparse(item["url"]).hostname,
        "connected": public_cctv_source_name(item) in existing,
    } for item in PUBLIC_CCTV_SOURCES]


@app.post("/v1/sources/public-cctv", status_code=201)
def create_public_cctv_source(body: PublicCctvInput, tenant: str = Depends(tenant_auth)):
    item = PUBLIC_CCTV_BY_ID.get(body.catalog_id)
    if not item:
        raise HTTPException(404, "Feed CCTV publik not found")
    with connect() as db:
        source = insert_public_cctv_source(db, tenant, item)
    if not source:
        raise HTTPException(409, "Feed CCTV publik is already connected")
    return {"sources": [source]}


@app.post("/v1/sources/public-cctv-catalog-pack", status_code=201)
def create_public_cctv_catalog_pack(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        created = [source for item in PUBLIC_CCTV_SOURCES
                   if (source := insert_public_cctv_source(db, tenant, item))]
    return {"sources": created, "total": len(PUBLIC_CCTV_SOURCES)}


@app.post("/v1/sources/public-bmkg", status_code=201)
def create_public_bmkg_sources(tenant: str = Depends(tenant_auth)):
    presets = [
        ("Weather in Kemayoran (BMKG)", "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=31.71.03.1001", "bmkg.weather", 3600),
        ("Latest Earthquake (BMKG)", "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json", "bmkg.earthquake.latest", 120),
        ("Felt Earthquake (BMKG)", "https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.json", "bmkg.earthquake.felt", 120),
    ]
    with connect() as db:
        existing = {row["name"] for row in db.execute(
            "SELECT name FROM sources WHERE tenant=? AND status!='deleted' AND name IN (?,?,?)",
            (tenant, *(name for name, _, _, _ in presets)),
        ).fetchall()}
        created = []
        for name, http_url, event_type, interval in presets:
            if name in existing:
                continue
            sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
            db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, name, "iot", hashlib.sha256(token.encode()).hexdigest(), "disabled", ts, None, interval))
            created.append({"id":sid,"name":name,"kind":"iot","status":"disabled","created_at":ts,"token":token,"http_url":http_url,"event_type":event_type,"interval_seconds":interval,"type":"http_json"})
    return {"sources":created,"already_connected":[name for name,_,_,_ in presets if name in existing]}


@app.get("/v1/public-sources/bmkg-weather")
def list_public_bmkg_weather_sources(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        existing = {row["name"] for row in db.execute(
            "SELECT name FROM sources WHERE tenant=? AND status!='deleted'",
            (tenant,),
        ).fetchall()}
    return [{
        "adm4_code": item["code"],
        "name": item["name"],
        "district": item["district"],
        "regency": item["regency"],
        "province": item["province"],
        "country": item["country"],
        "source_name": f"Weather in {item['name']}, {item['regency']} (BMKG)",
        "connected": f"Weather in {item['name']}, {item['regency']} (BMKG)" in existing,
    } for item in PUBLIC_BMKG_WEATHER_LOCATIONS]


@app.post("/v1/sources/public-bmkg-location", status_code=201)
def create_public_bmkg_weather_source(body: PublicBmkgLocationInput, tenant: str = Depends(tenant_auth)):
    item = PUBLIC_BMKG_WEATHER_BY_CODE.get(body.adm4_code)
    if not item:
        raise HTTPException(404, "BMKG weather location not found")
    name = f"Weather in {item['name']}, {item['regency']} (BMKG)"
    with connect() as db:
        existing = db.execute(
            "SELECT id FROM sources WHERE tenant=? AND name=? AND status!='deleted'",
            (tenant, name),
        ).fetchone()
        if existing:
            raise HTTPException(409, "BMKG weather feed for this location is already connected")
        sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
        db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, name, "iot", hashlib.sha256(token.encode()).hexdigest(), "disabled", ts, None, 3600))
    return {"sources":[{"id":sid,"name":name,"kind":"iot","status":"disabled","created_at":ts,"token":token,"http_url":f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={item['code']}","event_type":"bmkg.weather","interval_seconds":3600,"type":"http_json"}]}


@app.post("/v1/sources/public-bmkg-weather-pack", status_code=201)
def create_public_bmkg_weather_pack(tenant: str = Depends(tenant_auth)):
    names = [f"Weather in {item['name']}, {item['regency']} (BMKG)" for item in PUBLIC_BMKG_WEATHER_LOCATIONS]
    placeholders = ",".join("?" for _ in names)
    with connect() as db:
        existing = {row["name"] for row in db.execute(
            f"SELECT name FROM sources WHERE tenant=? AND status!='deleted' AND name IN ({placeholders})",
            (tenant, *names),
        ).fetchall()}
        created = []
        for item, name in zip(PUBLIC_BMKG_WEATHER_LOCATIONS, names):
            if name in existing:
                continue
            sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
            db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, name, "iot", hashlib.sha256(token.encode()).hexdigest(), "disabled", ts, None, 3600))
            created.append({"id":sid,"name":name,"kind":"iot","status":"disabled","created_at":ts,"token":token,"http_url":f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={item['code']}","event_type":"bmkg.weather","interval_seconds":3600,"type":"http_json"})
    return {"sources":created,"already_connected":[name for name in names if name in existing]}


@app.post("/v1/sources/public-global-pack", status_code=201)
def create_public_global_source_pack(tenant: str = Depends(tenant_auth)):
    presets = [
        ("Weather in Jakarta (Open-Meteo)", "https://api.open-meteo.com/v1/forecast?latitude=-6.2&longitude=106.8&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m", "openmeteo.current", 3600),
        ("Weather in Singapore (Open-Meteo)", "https://api.open-meteo.com/v1/forecast?latitude=1.35&longitude=103.82&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m", "openmeteo.current", 3600),
        ("Weather in Tokyo (Open-Meteo)", "https://api.open-meteo.com/v1/forecast?latitude=35.68&longitude=139.69&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m", "openmeteo.current", 3600),
        ("Significant Global Earthquakes (USGS)", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson", "usgs.earthquake.significant", 1800),
        ("Global Earthquakes in the Past 24 Hours (USGS)", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson", "usgs.earthquake.daily", 1800),
    ]
    with connect() as db:
        existing = {row["name"] for row in db.execute(
            "SELECT name FROM sources WHERE tenant=? AND status!='deleted' AND name IN (?,?,?,?,?)",
            (tenant, *(name for name, _, _, _ in presets)),
        ).fetchall()}
        created = []
        for name, http_url, event_type, interval in presets:
            if name in existing:
                continue
            sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
            db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, name, "iot", hashlib.sha256(token.encode()).hexdigest(), "disabled", ts, None, interval))
            created.append({"id":sid,"name":name,"kind":"iot","status":"disabled","created_at":ts,"token":token,"http_url":http_url,"event_type":event_type,"interval_seconds":interval,"type":"http_json"})
    return {"sources":created,"already_connected":[name for name,_,_,_ in presets if name in existing]}


@app.get("/v1/sources")
def list_sources(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        sources = [dict(row) for row in db.execute("SELECT id,name,kind,status,created_at,last_seen,expected_interval_seconds,automation_enabled,automation_interval_seconds FROM sources WHERE tenant=? AND status!='deleted' ORDER BY created_at DESC", (tenant,))]
        return [{**source, 'automation_enabled': bool(source['automation_enabled']), 'health': source_health(source)} for source in sources]


@app.put("/v1/sources/{sid}")
def update_source(sid: str, body: SourceUpdate, tenant: str = Depends(tenant_auth)):
    name, kind = body.name.strip(), body.kind.strip()
    if not name or not kind:
        raise HTTPException(422, "Source name and type are required")
    with connect() as db:
        cur = db.execute("UPDATE sources SET name=?,kind=?,status=?,expected_interval_seconds=?,automation_enabled=CASE WHEN ?='active' THEN automation_enabled ELSE 0 END WHERE id=? AND tenant=? AND status!='deleted'", (name, kind, body.status, body.expected_interval_seconds, body.status, sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Source not found")
    if body.status != 'active':
        with _pending_source_requests_lock:
            _pending_source_requests.pop(sid, None)
            _in_flight_source_requests.pop(sid, None)
    return {"id": sid, "name": name, "kind": kind, "status": body.status}


@app.put("/v1/sources/{sid}/automation")
def update_source_automation(sid: str, body: SourceAutomationUpdate, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        source = db.execute("SELECT kind FROM sources WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant)).fetchone()
        if not source:
            raise HTTPException(404, "Source not found")
        if source['kind'] not in ('camera', 'iot'):
            raise HTTPException(409, "Data automation is unavailable for this source type.")
        db.execute("UPDATE sources SET automation_enabled=?,automation_interval_seconds=?,status=CASE WHEN ?=1 THEN 'active' ELSE status END WHERE id=? AND tenant=?", (int(body.enabled), body.interval_seconds, int(body.enabled), sid, tenant))
        if body.enabled and source['kind'] == 'camera':
            db.execute("INSERT INTO source_media_settings (source_id,vision_enabled,audio_enabled,vision_prompt,audio_prompt) VALUES (?,1,0,?,?) ON CONFLICT(source_id) DO UPDATE SET vision_enabled=1", (sid, "Summarize visible road conditions and events without identifying people or vehicles. Estimate congestion and state when the image is unclear.", "Audio analysis is disabled."))
    return {"id": sid, "automation_enabled": body.enabled, "automation_interval_seconds": body.interval_seconds, "status": "active" if body.enabled else "unchanged"}


@app.post("/v1/sources/{sid}/request-data")
async def request_source_data(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        source = db.execute(
            "SELECT s.kind,s.status,m.vision_enabled FROM sources s LEFT JOIN source_media_settings m ON m.source_id=s.id WHERE s.id=? AND s.tenant=? AND s.status!='deleted'",
            (sid, tenant),
        ).fetchone()
    if not source:
        raise HTTPException(404, "Source not found")
    if source['kind'] not in ('camera', 'iot'):
        raise HTTPException(409, "This source type does not support one-time data requests.")
    with _pending_source_requests_lock:
        if sid in _pending_source_requests:
            requested_at, request_status = _pending_source_requests[sid], 'queued'
        else:
            requested_at, request_status = now(), 'queued'
            _pending_source_requests[sid] = requested_at
        waiter = _source_request_waiters.get(sid)
        if not waiter or waiter['requested_at'] != requested_at:
            waiter = {'requested_at': requested_at, 'event': asyncio.Event(), 'outcome': None}
            _source_request_waiters[sid] = waiter
    try:
        await asyncio.wait_for(waiter['event'].wait(), timeout=75)
        outcome = waiter['outcome'] or 'received'
        status = 'captured' if outcome == 'frame' else 'received'
    except asyncio.TimeoutError:
        status, outcome = 'timeout', None
        with _pending_source_requests_lock:
            if _pending_source_requests.get(sid) == requested_at:
                _pending_source_requests.pop(sid, None)
            current = _in_flight_source_requests.get(sid)
            if current and current[1] == requested_at:
                _in_flight_source_requests.pop(sid, None)
    finally:
        with _pending_source_requests_lock:
            if _source_request_waiters.get(sid) is waiter:
                _source_request_waiters.pop(sid, None)
    return {"status": status, "outcome": outcome, "source_status": source['status'], "requested_at": requested_at}


@app.delete("/v1/sources/{sid}")
def delete_source(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE sources SET status='deleted' WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Source not found")
    with _pending_source_requests_lock:
        _pending_source_requests.pop(sid, None)
        _in_flight_source_requests.pop(sid, None)
        _source_request_waiters.pop(sid, None)
    return {"status": "deleted"}


@app.get("/v1/sources/{sid}/events")
def source_events(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        if not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=?", (sid, tenant)).fetchone():
            raise HTTPException(404, "Source not found")
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in db.execute("SELECT * FROM source_events WHERE source_id=? ORDER BY rowid DESC LIMIT 50", (sid,))]


def export_rows(rows, fields, file_format, filename):
    if file_format == 'json':
        content, media_type = json.dumps(rows, ensure_ascii=False, indent=2), 'application/json; charset=utf-8'
    else:
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            values = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()}
            writer.writerow({key: ("'" + value if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r') else value) for key, value in values.items()})
        content, media_type = output.getvalue(), 'text/csv; charset=utf-8'
    return Response(content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{filename}.{file_format}"'})


@app.get('/v1/sources/{sid}/events/export')
def export_source_events(sid: str, format: str = Query(default='json', pattern='^(json|csv)$'), limit: int = Query(default=500, ge=1, le=1000), after: int = Query(default=0, ge=0), tenant: str = Depends(tenant_auth)):
    with connect() as db:
        if not db.execute('SELECT 1 FROM sources WHERE id=? AND tenant=?', (sid, tenant)).fetchone():
            raise HTTPException(404, 'Source not found')
        rows = [{**dict(row), 'payload': json.loads(row['payload'])} for row in db.execute('SELECT rowid AS cursor,id,source_id,event_type,payload,received_at FROM source_events WHERE source_id=? AND rowid>? ORDER BY rowid LIMIT ?', (sid, after, limit))]
    fields = ['cursor','id','source_id','event_type','received_at','payload']
    return export_rows(rows, fields, format, 'kanca-source-events')


def latest_source_observations(db, sid: str, tenant: str, event_type: str | None = None):
    source = db.execute("SELECT id,name,kind,status,last_seen FROM sources WHERE id=? AND tenant=? AND status='active'", (sid, tenant)).fetchone()
    if not source:
        raise HTTPException(404, "Source aktif not found")
    if event_type:
        rows = db.execute("SELECT event_type,payload,received_at FROM source_events WHERE source_id=? AND event_type=? ORDER BY rowid DESC LIMIT 10", (sid, event_type)).fetchall()
    else:
        rows = db.execute("SELECT event_type,payload,received_at FROM source_events WHERE source_id=? ORDER BY rowid DESC LIMIT 10", (sid,)).fetchall()
    events = [{"event_type": row["event_type"], "received_at": row["received_at"], "data": json.loads(row["payload"])} for row in rows]
    return dict(source), events


@app.post("/v1/sources/{sid}/query")
def query_source(sid: str, body: SourceQuestion, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        source, events = latest_source_observations(db, sid, tenant)
    try:
        question = body.question.strip()
        if not question:
            raise HTTPException(422, "Question must not kosong")
        answer = answer_source_question(question, source, events)
    except HTTPException:
        raise
    except PlanningError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"source": source, "answer": answer, "observations": len(events)}


@app.get("/v1/sources/{sid}/media-settings")
def get_media_settings(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        if not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant)).fetchone():
            raise HTTPException(404, "Source not found")
        row = db.execute("SELECT vision_enabled,audio_enabled,vision_prompt,audio_prompt FROM source_media_settings WHERE source_id=?", (sid,)).fetchone()
        if not row:
            return MediaSettings().model_dump()
        return {**dict(row), 'vision_enabled':bool(row['vision_enabled']), 'audio_enabled':bool(row['audio_enabled'])}


@app.put("/v1/sources/{sid}/media-settings")
def put_media_settings(sid: str, body: MediaSettings, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        if not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant)).fetchone():
            raise HTTPException(404, "Source not found")
        db.execute("INSERT INTO source_media_settings VALUES (?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET vision_enabled=excluded.vision_enabled,audio_enabled=excluded.audio_enabled,vision_prompt=excluded.vision_prompt,audio_prompt=excluded.audio_prompt", (sid, int(body.vision_enabled), int(body.audio_enabled), body.vision_prompt, body.audio_prompt))
    return body.model_dump()


@app.get("/v1/sources/{sid}/preview")
def get_source_preview(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        source = db.execute("SELECT kind FROM sources WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant)).fetchone()
    if not source:
        raise HTTPException(404, "Source not found")
    if source['kind'] != 'camera':
        raise HTTPException(409, "Preview is only available for camera sources.")
    with _source_previews_lock:
        preview = _source_previews.get(sid)
        if preview and preview['expires_at'] <= time.monotonic():
            _source_previews.pop(sid, None)
            preview = None
        if preview:
            content, mime, status, requested_at = preview['raw'], preview['mime'], preview['status'], preview['requested_at']
        else:
            content = mime = status = requested_at = None
    if content is None:
        raise HTTPException(404, "Belum ada cuplikan kamera baru.")
    return Response(content=content, media_type=mime, headers={
        "Cache-Control": "no-store, max-age=0",
        "X-Content-Type-Options": "nosniff",
        "X-Kanca-Preview-Status": status,
        "X-Kanca-Request-At": requested_at,
    })


@app.post("/v1/ingest/{sid}/media", status_code=202)
async def ingest_media(sid: str, request: Request, media_type: str = Query(pattern='^(vision|audio)$'), authorization: str = Header(default="")):
    supplied = authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else ''
    token_hash = hashlib.sha256(supplied.encode()).hexdigest()
    def authorized(db, lock=False):
        query = "SELECT s.tenant,s.status,s.token_hash,m.vision_enabled,m.audio_enabled,m.vision_prompt,m.audio_prompt FROM sources s JOIN source_media_settings m ON m.source_id=s.id WHERE s.id=? AND s.status!='deleted'"
        if lock and getattr(db, 'is_postgres', False): query += ' FOR UPDATE OF s,m'
        row = db.execute(query, (sid,)).fetchone()
        if not row or not supplied or not hmac.compare_digest(token_hash, row['token_hash']):
            raise HTTPException(401, 'Source credentials are invalid or media is not enabled')
        one_shot = media_type == 'vision' and one_shot_request_in_flight(sid)
        if row['status'] != 'active' and not one_shot:
            raise HTTPException(401, 'Source inactive')
        if not row[media_type + '_enabled'] and not one_shot:
            raise HTTPException(403, 'Media analysis is not enabled for this source')
        return row
    with connect() as db:
        settings = authorized(db)
        prompt, tenant = settings[media_type + '_prompt'], settings['tenant']
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > media.MAX_MEDIA_BYTES:
            raise HTTPException(413, 'Media melebihi batas 4 MiB')
        chunks.append(chunk)
    raw = b''.join(chunks)
    try:
        mime = media.validate_media(media_type, raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    preview_requested_at = one_shot_request_timestamp(sid) if media_type == 'vision' else None
    if preview_requested_at:
        store_source_preview(sid, preview_requested_at, raw, mime, 'analyzing')
        notify_source_request(sid, preview_requested_at, 'frame')
    try:
        async with media_slots:
            result = await media.analyze(media_type, raw, mime, prompt)
    except RuntimeError as exc:
        if preview_requested_at:
            update_source_preview_status(sid, preview_requested_at, 'failed')
            with _pending_source_requests_lock:
                current = _in_flight_source_requests.get(sid)
                if current and current[1] == preview_requested_at:
                    _in_flight_source_requests.pop(sid, None)
            notify_source_request(sid, preview_requested_at, 'frame')
        raise HTTPException(502, str(exc)) from exc
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = authorized(db, lock=True)
        if current[media_type + '_prompt'] != prompt:
            raise HTTPException(409, 'Analysis settings changed; result was not saved')
        eid, ts = uid('sevt'), now()
        db.execute('INSERT INTO source_events (id,source_id,event_type,payload,received_at) VALUES (?,?,?,?,?)', (eid, sid, 'media.' + media_type, json.dumps(result, ensure_ascii=False), ts))
        db.execute('UPDATE sources SET last_seen=? WHERE id=?', (ts, sid))
        event(db, tenant, '', 'source.event.v1', {'source_id':sid, 'source_event_id':eid, 'type':'media.' + media_type})
    if preview_requested_at:
        update_source_preview_status(sid, preview_requested_at, 'analyzed')
        notify_source_request(sid, preview_requested_at, 'received')
    with _pending_source_requests_lock:
        _in_flight_source_requests.pop(sid, None)
    return {'id':eid, 'status':'received', 'result':result}


@app.get("/v1/ingest/{sid}/status")
def ingest_source_status(sid: str, authorization: str = Header(default="")):
    supplied = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    with connect() as db:
        source = db.execute("SELECT s.token_hash,s.status,s.kind,s.automation_enabled,s.automation_interval_seconds,m.vision_enabled,m.audio_enabled FROM sources s LEFT JOIN source_media_settings m ON m.source_id=s.id WHERE s.id=? AND s.status!='deleted'", (sid,)).fetchone()
    if not source or not supplied or not hmac.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(), source["token_hash"]):
        raise HTTPException(401, "Invalid source credentials")
    active = source["status"] == "active"
    vision_enabled = bool(source["vision_enabled"])
    with _pending_source_requests_lock:
        requested = sid in _pending_source_requests
        if requested:
            requested_at = _pending_source_requests.pop(sid)
            _in_flight_source_requests[sid] = (time.monotonic(), requested_at)
    return {
        "active": active or requested,
        "vision_enabled": vision_enabled or (requested and source["kind"] == "camera"),
        "audio_enabled": bool(source["audio_enabled"]),
        "capture_requested": requested,
        "automation_enabled": bool(source["automation_enabled"]),
        "automation_interval_seconds": source["automation_interval_seconds"],
    }


@app.post("/v1/ingest/{sid}", status_code=202)
async def ingest(sid: str, request: Request, authorization: str = Header(default="")):
    supplied = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 32768:
            raise HTTPException(413, "Data terlalu besar")
        chunks.append(chunk)
    try:
        def parse_finite_float(value):
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("invalid JSON number")
            return number
        payload = json.loads(
            b"".join(chunks),
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON constant")),
            parse_float=parse_finite_float,
        )
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(422, "Data must be JSON")
    if not isinstance(payload, dict) or not isinstance(payload.get("type"), str) or not 1 <= len(payload["type"]) <= 100 or not isinstance(payload.get("data"), dict):
        raise HTTPException(422, "Send an object with type and data")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        source_query = "SELECT * FROM sources WHERE id=? AND status!='deleted'"
        if getattr(db, 'is_postgres', False): source_query += ' FOR UPDATE'
        source = db.execute(source_query, (sid,)).fetchone()
        if not source or not supplied or not hmac.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(), source["token_hash"]):
            raise HTTPException(401, "Invalid source credentials")
        if source['status'] != 'active' and not one_shot_request_in_flight(sid):
            raise HTTPException(401, "Source inactive")
        eid, ts = uid("sevt"), now()
        db.execute("INSERT INTO source_events (id,source_id,event_type,payload,received_at) VALUES (?,?,?,?,?)", (eid, sid, payload["type"], json.dumps(payload["data"], ensure_ascii=False), ts))
        db.execute("UPDATE sources SET last_seen=? WHERE id=?", (ts, sid))
        event(db, source["tenant"], "", "source.event.v1", {"source_id": sid, "source_event_id": eid, "type": payload["type"]})
    requested_at = one_shot_request_timestamp(sid)
    with _pending_source_requests_lock:
        _in_flight_source_requests.pop(sid, None)
    notify_source_request(sid, requested_at, 'received')
    return {"id": eid, "status": "received"}


@app.post("/v1/connections", status_code=201)
def create_connection(body: ConnectionRequest, tenant: str = Depends(tenant_auth)):
    if body.type not in {"business_demo", "device_demo"}:
        raise HTTPException(400, "Connector unavailable")
    item = {"id": uid("conn"), "type": body.type, "status": "connected", "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO connections (id,tenant,type,status,created_at,name,config,credentials_enc) VALUES (?,?,?,?,?,?,?,?)", (item["id"], tenant, item["type"], item["status"], item["created_at"], None, '{}', None))
    return item


@app.post("/v1/erp-connections/odoo", status_code=201)
def create_odoo_connection(body: OdooConnectionRequest, tenant: str = Depends(tenant_auth)):
    try:
        base_url = validate_base_url(body.base_url)
        credentials_enc = encrypt_credentials({"api_key": body.api_key})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    item = {"id": uid("conn"), "type": "erp_odoo", "status": "pending", "name": body.name.strip(), "created_at": now()}
    if not item["name"]:
        raise HTTPException(422, "Connection name is required")
    config = {"base_url": base_url, "database": body.database}
    with connect() as db:
        db.execute("INSERT INTO connections (id,tenant,type,status,created_at,name,config,credentials_enc) VALUES (?,?,?,?,?,?,?,?)", (item["id"], tenant, item["type"], item["status"], item["created_at"], item["name"], json.dumps(config), credentials_enc))
    return item


@app.post("/v1/erp-connections/demo", status_code=201)
def create_demo_erp_connection(tenant: str = Depends(tenant_auth)):
    item = {"id": uid("conn"), "type": "erp_demo", "status": "connected", "name": "ERP Demo Gudang", "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO connections (id,tenant,type,status,created_at,name,config,credentials_enc) VALUES (?,?,?,?,?,?,?,?)", (item["id"], tenant, item["type"], item["status"], item["created_at"], item["name"], json.dumps(erp_demo.default_state(), ensure_ascii=False), None))
    return {**item, "simulated": True}


@app.post("/v1/erp-connections/{connection_id}/reset-demo")
def reset_demo_erp_connection(connection_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE connections SET config=? WHERE id=? AND tenant=? AND type='erp_demo' AND status='connected'", (json.dumps(erp_demo.default_state(), ensure_ascii=False), connection_id, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Active demo ERP connection not found")
    return {"status": "reset", "simulated": True}


@app.post("/v1/erp-connections/{connection_id}/test")
def test_erp_connection(connection_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        row = db.execute("SELECT type,status,config,credentials_enc FROM connections WHERE id=? AND tenant=?", (connection_id, tenant)).fetchone()
    if not row:
        raise HTTPException(404, "Connection not found")
    if row["type"] != "erp_odoo" or row["status"] not in {"pending", "connected"}:
        raise HTTPException(409, "Odoo connection is not available for testing")
    try:
        config = json.loads(row["config"] or '{}')
        credentials = decrypt_credentials(row["credentials_enc"] or '')
        result = OdooClient(config["base_url"], credentials["api_key"], config.get("database")).test()
        with connect() as db:
            db.execute("UPDATE connections SET status='connected' WHERE id=? AND tenant=?", (connection_id, tenant))
        return result
    except (ValueError, KeyError, OdooError) as exc:
        raise HTTPException(502, f"Odoo connection check failed: {exc}") from exc


@app.get("/v1/connections")
def connections(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id,type,status,created_at,name FROM connections WHERE tenant=?", (tenant,))]


@app.delete("/v1/connections/{connection_id}")
def revoke(connection_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE connections SET status='revoked',credentials_enc=NULL WHERE id=? AND tenant=?", (connection_id, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Connection not found")
    return {"status": "revoked"}


@app.get("/v1/connections/{connection_id}/resources")
def resources(connection_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        row = db.execute("SELECT type,status FROM connections WHERE id=? AND tenant=?", (connection_id, tenant)).fetchone()
    if not row:
        raise HTTPException(404, "Connection not found")
    caps = describe(row["type"])
    if row["type"] == "erp_odoo":
        caps = [item for item in describe("erp") if item["name"].startswith("erp.odoo.")]
    return {"connection_id": connection_id, "status": row["status"], "capabilities": caps if row["status"] == "connected" else []}


@app.post("/v1/tasks", status_code=201)
def create_task(body: TaskRequest, idempotency_key: str | None = Header(default=None, max_length=200), tenant: str = Depends(tenant_auth)):
    return create_task_internal(body, idempotency_key, tenant)


def connected_capabilities(db, tenant):
    has_connected_erp = db.execute("SELECT 1 FROM connections WHERE tenant=? AND type IN ('erp_odoo','erp_demo') AND status='connected' LIMIT 1", (tenant,)).fetchone()
    has_demo_erp = db.execute("SELECT 1 FROM connections WHERE tenant=? AND type='erp_demo' LIMIT 1", (tenant,)).fetchone()
    if not has_connected_erp and not has_demo_erp:
        demo = {"id": uid("conn"), "type": "erp_demo", "status": "connected", "name": "ERP Demo Gudang", "created_at": now()}
        db.execute("INSERT INTO connections (id,tenant,type,status,created_at,name,config,credentials_enc) VALUES (?,?,?,?,?,?,?,?)", (demo["id"], tenant, demo["type"], demo["status"], demo["created_at"], demo["name"], json.dumps(erp_demo.default_state(), ensure_ascii=False), None))
    has_demo_erp = db.execute("SELECT 1 FROM connections WHERE tenant=? AND type='erp_demo' AND status='connected' LIMIT 1", (tenant,)).fetchone()
    has_demo_gateway = db.execute("SELECT 1 FROM sources WHERE tenant=? AND name='Gateway Penerimaan Gudang Demo' LIMIT 1", (tenant,)).fetchone()
    if has_demo_erp and not has_demo_gateway:
        sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
        db.execute("INSERT INTO sources (id,tenant,name,kind,token_hash,status,created_at,last_seen,expected_interval_seconds) VALUES (?,?,?,?,?,?,?,?,?)", (sid, tenant, "Gateway Penerimaan Gudang Demo", "iot", hashlib.sha256(token.encode()).hexdigest(), "active", ts, ts, 90))
    connected = {r[0] for r in db.execute("SELECT type FROM connections WHERE tenant=? AND status='connected'", (tenant,))}
    if "erp_odoo" in connected:
        connected.add("erp")
    sources = db.execute("SELECT id,name,kind FROM sources WHERE tenant=? AND status='active'", (tenant,)).fetchall()
    if sources:
        connected.add("external_events")
    available = [item for item in describe() if item["connector"] in connected or (item["connector"] == "erp" and "erp_odoo" in connected and item["name"].startswith("erp.odoo."))]
    erp_connections = [dict(r) for r in db.execute("SELECT id,type,name,status FROM connections WHERE tenant=? AND status='connected' AND type IN ('erp_odoo','erp_demo')", (tenant,))]
    for item in available:
        if item["name"].startswith("erp."):
            expected_type = "erp_demo" if item["name"].startswith("erp.demo.") else "erp_odoo"
            item["available_connections"] = [connection for connection in erp_connections if connection["type"] == expected_type]
    for item in available:
        if item["name"] in {"external.latest_event", "erp.demo.reconcile_source_receipt"}:
            source_info = []
            for row in sources:
                source = dict(row)
                source['event_types'] = [item[0] for item in db.execute('SELECT DISTINCT event_type FROM source_events WHERE source_id=? ORDER BY event_type LIMIT 30', (row['id'],))]
                latest = db.execute("SELECT payload FROM source_events WHERE source_id=? ORDER BY rowid DESC LIMIT 1", (row["id"],)).fetchone()
                if latest:
                    def fields(data, prefix="data", depth=0):
                        result = []
                        if depth > 2 or not isinstance(data, dict):
                            return result
                        for key, value in list(data.items())[:30]:
                            if not isinstance(key, str) or not key.replace('_', '').isalnum() or len(key) > 50:
                                continue
                            path = prefix + "." + key
                            if isinstance(value, dict):
                                result.extend(fields(value, path, depth + 1))
                            elif isinstance(value, (str, int, float, bool)) and value is not None:
                                result.append({"field": path, "type": "boolean" if isinstance(value, bool) else "number" if isinstance(value, (int, float)) else "string"})
                        return result
                    source["observed_fields"] = fields(json.loads(latest["payload"]))
                    source["fields_by_event_type"] = {}
                    for event_type in source['event_types']:
                        typed = db.execute('SELECT payload FROM source_events WHERE source_id=? AND event_type=? ORDER BY rowid DESC LIMIT 1', (row['id'], event_type)).fetchone()
                        if typed:
                            source['fields_by_event_type'][event_type] = fields(json.loads(typed['payload']))
                source_info.append(source)
            item["available_sources"] = source_info
    return connected, available


def create_task_internal(body: TaskRequest, idempotency_key: str | None, tenant: str, proposed: dict | None = None, auto_approve_safe: bool = False):
    with connect() as db:
        if idempotency_key:
            existing = db.execute("SELECT * FROM tasks WHERE tenant=? AND idempotency_key=?", (tenant, idempotency_key)).fetchone()
            if existing:
                old = json.loads(existing["plan"])
                request_hash = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
                if old.get("request_hash") != request_hash:
                    raise HTTPException(409, "Idempotency-Key has already been used for another request")
                return task_dict(existing)
        connected, available = connected_capabilities(db, tenant)
        if body.explicit_steps is not None and proposed is None:
            plan = {"summary": "Explicit plan from user (demo mode).", "steps": [s.model_dump(exclude_none=True) for s in body.explicit_steps], "source": "explicit"}
        else:
            try:
                plan = proposed if proposed is not None else propose(body.instruction, available)
            except PlanningError as exc:
                raise HTTPException(503, str(exc)) from exc
            if not isinstance(plan, dict):
                raise HTTPException(422, "The model returned an invalid plan")
            if not plan.get("steps"):
                raise HTTPException(422, {"clarification": plan.get("clarification") or "The instruction cannot be planned with the available capabilities."})
            try:
                model_schedule = Schedule.model_validate(plan.get("schedule") or {"interval_seconds": 1, "max_runs": 1})
            except ValueError as exc:
                raise HTTPException(422, "The schedule returned by the model is invalid") from exc
            plan = {"summary": str(plan.get("summary", "Plan agent")), "steps": plan["steps"], "source": "baseten", "schedule": model_schedule.model_dump()}
        try:
            validate_steps(plan["steps"], connected)
            for step in plan["steps"]:
                source_required = step["capability"] in {"external.latest_event", "erp.demo.reconcile_source_receipt"}
                source_query = "SELECT kind FROM sources WHERE id=? AND tenant=? AND status='active'" + (" AND kind='iot'" if step["capability"] == "erp.demo.reconcile_source_receipt" else "")
                source_row = db.execute(source_query, (step["arguments"]["source_id"], tenant)).fetchone() if source_required else True
                if not source_row:
                    raise ValueError("The requested source is inactive or unavailable.")
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        plan["request_hash"] = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        if body.schedule is not None:
            plan["schedule"] = body.schedule.model_dump()
        elif "schedule" not in plan:
            plan["schedule"] = {"interval_seconds": 1, "max_runs": 1}
        tid, ts = uid("task"), now()
        auto_start = auto_approve_safe and all(CAPABILITIES[step['capability']].get('risk') in ('read', 'safe_action') for step in plan['steps'])
        initial_status = 'scheduled' if auto_start else 'awaiting_approval'
        try:
            db.execute("INSERT INTO tasks (id,tenant,instruction,status,plan,version,result,created_at,updated_at,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?,?)", (tid, tenant, body.instruction, initial_status, json.dumps(plan, ensure_ascii=False), 1, None, ts, ts, idempotency_key))
            db.execute("INSERT INTO schedules (task_id,interval_seconds,max_runs,next_run) VALUES (?,?,?,?)", (tid, plan["schedule"]["interval_seconds"], plan["schedule"]["max_runs"], ts))
            event(db, tenant, tid, "task.created.v1", {})
            if auto_start:
                event(db, tenant, tid, "task.approved.v1", {"version": 1, "mode": "automatic_safe"})
                acquire_task_source_automation(db, tid, tenant, plan)
            else:
                event(db, tenant, tid, "task.approval_requested.v1", {"version": 1})
        except INTEGRITY_ERRORS:
            db.rollback()
            if idempotency_key:
                existing = db.execute("SELECT * FROM tasks WHERE tenant=? AND idempotency_key=?", (tenant, idempotency_key)).fetchone()
                if existing:
                    if json.loads(existing["plan"]).get("request_hash") != plan["request_hash"]:
                        raise HTTPException(409, "Idempotency-Key has already been used for another request")
                    return task_dict(existing)
            raise
        row = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    return task_dict(row)


def get_conversation(db, cid, tenant):
    row = db.execute("SELECT * FROM conversations WHERE id=? AND tenant=? AND status!='deleted'", (cid, tenant)).fetchone()
    if row is None:
        raise HTTPException(404, "Percakapan not found")
    return row


@app.post("/v1/conversations", status_code=201)
def create_conversation(body: ConversationRequest, tenant: str = Depends(tenant_auth)):
    cid, ts = uid("chat"), now()
    title = body.title.strip() or "Percakapan baru"
    with connect() as db:
        db.execute("INSERT INTO conversations (id,tenant,title,created_at,updated_at,status) VALUES (?,?,?,?,?,?)", (cid, tenant, title, ts, ts, 'active'))
    return {"id": cid, "title": title, "created_at": ts, "updated_at": ts, "status": "active"}


@app.get("/v1/conversations")
def conversations(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT id,title,status,created_at,updated_at FROM conversations WHERE tenant=? AND status!='deleted' ORDER BY updated_at DESC, rowid DESC LIMIT 100", (tenant,))]


@app.delete("/v1/conversations")
def clear_conversation_history(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute(
            "UPDATE conversations SET status='deleted',updated_at=? WHERE tenant=? AND status!='deleted'",
            (now(), tenant),
        )
    return {"status": "cleared", "deleted_count": cur.rowcount}


@app.patch("/v1/conversations/{cid}")
def update_conversation(cid: str, body: ConversationUpdate, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        get_conversation(db, cid, tenant)
        db.execute("UPDATE conversations SET status=?,updated_at=? WHERE id=? AND tenant=? AND status!='deleted'", (body.status, now(), cid, tenant))
    return {"id": cid, "status": body.status}


@app.delete("/v1/conversations/{cid}")
def delete_conversation(cid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE conversations SET status='deleted',updated_at=? WHERE id=? AND tenant=? AND status!='deleted'", (now(), cid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Percakapan not found")
    return {"id": cid, "status": "deleted"}


@app.get("/v1/conversations/{cid}/messages")
def conversation_messages(cid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        get_conversation(db, cid, tenant)
        rows = db.execute("SELECT id,role,content,task_id,created_at FROM messages WHERE conversation_id=? ORDER BY rowid", (cid,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item["task_id"]:
                task = db.execute("SELECT * FROM tasks WHERE id=? AND tenant=?", (item["task_id"], tenant)).fetchone()
                item["task"] = task_dict(task) if task else None
            result.append(item)
        return result


def integration_status_answer(text: str, tenant: str) -> str | None:
    normalized = text.casefold()
    integration_words = r"integrasi|integration|source|sumber|kamera|camera|mqtt|bluetooth|\bble\b|home assistant|sensor|perangkat|device"
    status_words = r"cek|check|periksa|status|aktif|active|online|terhubung|connected|jalan|running|berfungsi|working|data terbaru|latest data|kondisi|status"
    if not re.search(integration_words, normalized) or not re.search(status_words, normalized):
        return None
    camera_query = bool(re.search(r"kamera|rtsp|\bcamera\b", normalized))
    english = bool(re.search(r"\b(check|camera|device|integration|source|active|online|connected|working|latest|status)\b", normalized))
    with connect() as db:
        sources = [dict(r) for r in db.execute("SELECT id,name,kind,status,last_seen FROM sources WHERE tenant=? AND status!='deleted' ORDER BY created_at DESC", (tenant,))]
        sources = [s for s in sources if not camera_query or re.search(r"kamera|camera|rtsp", f"{s['name']} {s['kind']}", re.I)]
        if not sources:
            if camera_query:
                return "No camera source is registered in Kanca. Add one under Integrations → External sources." if english else "No camera source is registered in Kanca. Add one under Integrations → External Sources."
            return "No integrations or external sources are registered in Kanca." if english else "No integrations or external sources are registered in Kanca."
        lines = []
        for source in sources:
            latest = db.execute("SELECT event_type,received_at,payload FROM source_events WHERE source_id=? ORDER BY rowid DESC LIMIT 1", (source['id'],)).fetchone()
            label = source['name']
            if source['status'] != 'active':
                lines.append(f"{label}: inactive in Kanca." if english else f"{label}: nonaktif di Kanca.")
                continue
            if latest:
                age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(latest['received_at'])).total_seconds())
                freshness = ("just now" if age <= 300 else f"{int(age // 60)} minutes ago") if english else ("baru saja" if age <= 300 else f"terakhir {int(age // 60)} menit lalu")
                data = json.loads(latest['payload'])
                detail = data.get('summary') if isinstance(data, dict) else None
                if not detail and isinstance(data, dict):
                    detail = data.get('state') or data.get('value')
                suffix = (f" Summary: {detail}" if english else f" Ringkasan: {detail}") if detail else ""
                lines.append(f"{label}: active in Kanca; data received {freshness} ({latest['event_type']}).{suffix}" if english else f"{label}: aktif di Kanca dan ada data ({freshness}, {latest['event_type']}).{suffix}")
            elif source['last_seen']:
                lines.append(f"{label}: active in Kanca, but no data is stored yet." if english else f"{label}: is active in Kanca, but no data has been stored yet.")
            else:
                lines.append(f"{label}: registered and enabled in Kanca, but has never sent data. The physical device status cannot be confirmed." if english else f"{label}: is registered and enabled in Kanca, but has never sent data. The physical device status cannot be confirmed.")
        if camera_query and all(s['status'] != 'active' for s in sources):
            return ("Camera sources are registered, but all are inactive in Kanca. " if english else "Source kamera terdaftar, tetapi semuanya nonaktif di Kanca. ") + " ".join(lines)
        return "\n".join(lines)


def integration_inventory_answer(text: str, tenant: str) -> str | None:
    normalized = text.casefold()
    asks_inventory = re.search(r"perangkat apa|apa saja.*(perangkat|integrasi|sumber)|perangkat.*(terhubung|terintegrasi)|integrasi apa|sumber apa|what (devices|integrations|sources)|which (devices|integrations|sources)|devices?.*(connected|integrated)|integrations?.*(connected|available)|what is connected", normalized)
    if not asks_inventory:
        return None
    english = bool(re.search(r"\b(what|which|devices|integrations|sources|connected|integrated)\b", normalized))
    with connect() as db:
        sources = [dict(r) for r in db.execute("SELECT id,name,kind,status,last_seen FROM sources WHERE tenant=? AND status!='deleted' ORDER BY created_at DESC", (tenant,))]
        connections = [dict(r) for r in db.execute("SELECT type,status FROM connections WHERE tenant=? ORDER BY created_at DESC", (tenant,))]
        names = {s['name'] for s in sources}
        names.update(c['type'].replace('_',' ').title() for c in connections if c['status']=='connected')
        if not names:
            return "No devices or integrations are connected yet." if english else "No devices or integrations are connected yet."
        header = "These devices and integrations are registered in Kanca:" if english else "These devices and integrations are registered in Kanca:"
        lines = []
        for source in sources:
            kind = source['kind'].replace('_',' ').upper()
            state = ("enabled" if source['status']=='active' else "disabled") if english else ("aktif" if source['status']=='active' else "nonaktif")
            lines.append(f"• {source['name']} ({kind}) — {state}")
        for connection in connections:
            if connection['status']=='connected':
                lines.append(f"• {connection['type'].replace('_',' ').title()} — " + ("connected" if english else "terhubung"))
        caveat = "\nThis reports Kanca's configuration; it does not prove a physical device is online." if english else "\nThis shows Kanca configuration; it does not prove a physical device is online."
        return header + "\n" + "\n".join(lines) + caveat


def task_history_answer(text: str, tenant: str) -> str | None:
    normalized = text.casefold()
    english = bool(re.search(r"\b(tasks?|history|previous|recent|last|ran)\b", normalized))
    if not re.search(r"tugas|task|riwayat|history|sebelumnya|terakhir|previous|recent|last", normalized):
        return None
    if not re.search(r"cek|lihat|tampilkan|apa|bagaimana|status|riwayat|history|sebelumnya|terakhir|pernah|berjalan", normalized):
        return None
    status_labels = {"awaiting_approval":"awaiting approval", "scheduled":"scheduled", "running":"running", "paused":"paused", "completed":"completed", "failed":"failed", "cancelled":"cancelled"}
    with connect() as db:
        rows = db.execute("SELECT id,instruction,status,result,created_at,updated_at FROM tasks WHERE tenant=? AND archived=0 ORDER BY created_at DESC LIMIT 5", (tenant,)).fetchall()
        if not rows:
            return "There are no saved tasks in Kanca yet." if english else "Belum ada tugas tersimpan di Kanca."
        lines = []
        for row in rows:
            runs = db.execute("SELECT COUNT(*) FROM task_runs WHERE task_id=?", (row['id'],)).fetchone()[0]
            when = datetime.fromisoformat(row['updated_at']).astimezone().strftime('%d %b %Y %H:%M')
            line = f"• {row['instruction']} — {status_labels.get(row['status'], row['status'])}; diperbarui {when}"
            if runs:
                line += f"; checked {runs} kali"
            if row['status'] == 'failed' and row['result']:
                detail = json.loads(row['result']).get('error')
                if detail:
                    line += f". Note: {detail}"
            lines.append(line)
        if english:
            lines = [line.replace("diperbarui","updated").replace("checked","checked").replace("kali","times").replace("Note:","Note:") for line in lines]
            return "Here are up to 5 recent tasks:\n" + "\n".join(lines)
        return "Berikut hingga 5 tugas terbaru:\n" + "\n".join(lines)


def route_chat_source_request(question: str, tenant: str):
    with connect() as db:
        sources = [dict(row) for row in db.execute(
            "SELECT id,name,kind,status FROM sources WHERE tenant=? AND kind IN ('camera','iot') AND status='active' ORDER BY name",
            (tenant,),
        )]
    if not sources:
        return None
    route = route_source_data_request(question, sources)
    valid_ids = {source['id'] for source in sources}
    route['source_ids'] = list(dict.fromkeys(sid for sid in route['source_ids'] if sid in valid_ids))
    if route['route'] == 'fetch' and not route['source_ids']:
        return {'route': 'clarify', 'reply': route['reply'] or 'Which source would you like to check?'}
    return route


def wait_for_source_events(requested: list[tuple[dict, str]], timeout_seconds: int = 60):
    pending = {source['id']: (source, requested_at) for source, requested_at in requested}
    observations = []
    deadline = time.monotonic() + timeout_seconds
    while pending and time.monotonic() < deadline:
        with connect() as db:
            for source_id, (source, requested_at) in list(pending.items()):
                if source['kind'] == 'camera':
                    event_row = db.execute(
                        "SELECT event_type,payload,received_at FROM source_events WHERE source_id=? AND event_type='media.vision' AND received_at>=? ORDER BY rowid DESC LIMIT 1",
                        (source_id, requested_at),
                    ).fetchone()
                else:
                    event_row = db.execute(
                        "SELECT event_type,payload,received_at FROM source_events WHERE source_id=? AND received_at>=? ORDER BY rowid DESC LIMIT 1",
                        (source_id, requested_at),
                    ).fetchone()
                if event_row:
                    observations.append({
                        'source_id': source_id,
                        'source_name': source['name'],
                        'event_type': event_row['event_type'],
                        'received_at': event_row['received_at'],
                        'data': json.loads(event_row['payload']),
                    })
                    pending.pop(source_id)
        if pending:
            time.sleep(0.75)
    return observations, [source['name'] for source, _ in pending.values()]


async def answer_routed_source_chat(question: str, tenant: str, source_ids: list[str]):
    with connect() as db:
        sources = [dict(row) for source_id in source_ids for row in [db.execute(
            "SELECT id,name,kind,status FROM sources WHERE id=? AND tenant=? AND status!='deleted'",
            (source_id, tenant),
        ).fetchone()] if row]
    if not sources:
        return "I could not find a matching data source for that request."
    requested = []
    timed_out = []
    for source in sources:
        result = await request_source_data(source['id'], tenant)
        if result['status'] == 'timeout':
            timed_out.append(source['name'])
            continue
        requested.append((source, result['requested_at']))
    observations, unavailable = await asyncio.to_thread(wait_for_source_events, requested)
    unavailable = list(dict.fromkeys([*unavailable, *timed_out]))
    if not observations:
        names = ', '.join(unavailable)
        return f"I have not received new data from {names}. Check the gateway connection and source availability, then try again."
    answer = answer_source_question(question, {'sources': sources}, observations)
    if unavailable:
        answer += "\n\nNo new data from: " + ', '.join(unavailable) + "."
    return answer


@app.post("/v1/conversations/{cid}/messages", status_code=201)
async def send_message(cid: str, body: MessageRequest, tenant: str = Depends(tenant_auth)):
    content = body.content.strip()
    if not content:
        raise HTTPException(422, "Pesan must not kosong")
    with connect() as db:
        conversation = get_conversation(db, cid, tenant)
        rows = db.execute("SELECT role,content FROM messages WHERE conversation_id=? ORDER BY rowid DESC LIMIT 12", (cid,)).fetchall()
        history = [dict(row) for row in reversed(rows)]
        connected, available = connected_capabilities(db, tenant)
        ts = now()
        db.execute("INSERT INTO messages (id,conversation_id,role,content,task_id,created_at) VALUES (?,?,?,?,?,?)", (uid("msg"), cid, "user", content, None, ts))
        title = content[:70] if conversation["title"] == "Percakapan baru" else conversation["title"]
        db.execute("UPDATE conversations SET title=?,updated_at=? WHERE id=?", (title, ts, cid))
    source_route = None
    try:
        source_route = route_chat_source_request(content, tenant)
    except PlanningError:
        # Do not guess a source or initiate an external request when intent parsing fails.
        source_route = {'route': 'unavailable', 'reply': 'Sorry, I cannot identify the source you mean. Please try again shortly.'}
    planning_available = available
    if source_route and source_route.get('route') == 'continue' and source_route.get('requires_source'):
        allowed_source_ids = set(source_route.get('source_ids') or [])
        if not allowed_source_ids:
            source_route = {'route': 'clarify', 'reply': 'Please connect a suitable data source before setting up this monitoring task.'}
        else:
            planning_available = []
            for capability in available:
                if capability.get('name') not in {'external.latest_event', 'erp.demo.reconcile_source_receipt'}:
                    planning_available.append(capability)
                    continue
                matching_sources = [source for source in capability.get('available_sources', []) if source.get('id') in allowed_source_ids]
                if matching_sources:
                    planning_available.append({**capability, 'available_sources': matching_sources})
    is_source_monitoring_task = bool(source_route and source_route.get('route') == 'continue' and source_route.get('requires_source'))
    direct_answer = None if is_source_monitoring_task else (
        integration_status_answer(content, tenant)
        or integration_inventory_answer(content, tenant)
        or task_history_answer(content, tenant)
    )
    try:
        if source_route and source_route['route'] == 'fetch':
            answer, task_id = await answer_routed_source_chat(content, tenant, source_route['source_ids']), None
        elif source_route and source_route['route'] in {'clarify', 'unavailable'}:
            answer, task_id = source_route['reply'], None
        elif direct_answer is not None:
            answer, task_id = direct_answer, None
        else:
            plan = propose(content, planning_available, history)
            for attempt in range(2):
                if not isinstance(plan, dict):
                    raise ValueError("The model returned an invalid response.")
                if not plan.get("steps"):
                    answer = str(plan.get("answer") or plan.get("clarification") or "Could you share a little more detail about what you need?")
                    task_id = None
                    break
                schedule = plan.get("schedule")
                source_read_only = (isinstance(plan["steps"], list) and bool(plan["steps"])
                                    and all(isinstance(step, dict) and step.get("capability") == "external.latest_event" for step in plan["steps"]))
                one_shot = not isinstance(schedule, dict) or schedule.get("max_runs", 1) == 1
                if source_read_only and one_shot:
                    try:
                        validate_steps(plan["steps"], connected)
                        observations, source_context = [], []
                        for step in plan["steps"]:
                            args = step["arguments"]
                            with connect() as source_db:
                                source, events = latest_source_observations(source_db, args["source_id"], tenant, args.get("event_type"))
                            source_context.append(source)
                            observations.extend({**item, "source_id": source["id"], "source_name": source["name"]} for item in events[:1])
                        answer = answer_source_question(content, {"sources": source_context}, observations)
                        task_id = None
                        break
                    except HTTPException as exc:
                        if exc.status_code != 422 or attempt:
                            raise
                        plan = propose(content, planning_available, history, feedback=f"Previous plan rejected: {exc.detail}. Choose the correct active source or ask for clarification.")
                        continue
                try:
                    task = create_task_internal(TaskRequest(instruction=content), None, tenant, proposed=plan, auto_approve_safe=True)
                except HTTPException as exc:
                    if exc.status_code != 422 or attempt:
                        raise
                    plan = propose(content, planning_available, history, feedback=f"Previous plan rejected: {exc.detail}. Fix the format using available data or ask for clarification.")
                    continue
                answer = "Okay, I will work on it. The result will appear here." if task['status'] == 'scheduled' else "I have prepared a plan. Please review and approve it before I start."
                task_id = task["id"]
                break
    except PlanningError as exc:
        answer, task_id = "Sorry, I cannot answer right now. Please try again shortly.", None
    except (ValueError, HTTPException) as exc:
        answer, task_id = "Sorry, I cannot create a plan that matches the connected devices. Make sure the required source is connected, then try again with a clear time and condition.", None
    msg = {"id": uid("msg"), "role": "assistant", "content": answer, "task_id": task_id, "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO messages (id,conversation_id,role,content,task_id,created_at) VALUES (?,?,?,?,?,?)", (msg["id"], cid, msg["role"], answer, task_id, msg["created_at"]))
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (msg["created_at"], cid))
    return msg


def get_task_row(db, tid, tenant, lock=False):
    query = "SELECT * FROM tasks WHERE id=? AND tenant=?"
    if lock and getattr(db, 'is_postgres', False): query += ' FOR UPDATE'
    row = db.execute(query, (tid, tenant)).fetchone()
    if row is None:
        raise HTTPException(404, "Task not found")
    return row


@app.get("/v1/tasks/{tid}")
def get_task(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return task_dict(get_task_row(db, tid, tenant))


@app.get("/v1/tasks")
def list_tasks(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [task_dict(row) for row in db.execute("SELECT * FROM tasks WHERE tenant=? AND archived=0 ORDER BY created_at DESC LIMIT 100", (tenant,))]


@app.post("/v1/tasks/{tid}/rerun", status_code=201)
def rerun_task(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        original = get_task_row(db, tid, tenant, lock=True)
        if original['archived'] or original['status'] not in ('completed', 'failed', 'cancelled'):
            raise HTTPException(409, "Only completed, failed, or stopped tasks can be rerun")
        plan = json.loads(original['plan'])
        connected, _ = connected_capabilities(db, tenant)
        try:
            validate_steps(plan['steps'], connected)
            for step in plan['steps']:
                if step['capability'] in {'external.latest_event', 'erp.demo.reconcile_source_receipt'}:
                    source_query = "SELECT kind FROM sources WHERE id=? AND tenant=? AND status='active'" + (" AND kind='iot'" if step['capability'] == 'erp.demo.reconcile_source_receipt' else "")
                    if not db.execute(source_query, (step['arguments']['source_id'], tenant)).fetchone():
                        raise ValueError("Source inactive or not suitable for ERP receipt reconciliation")
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        plan.pop('request_hash', None)
        plan['rerun_of'] = tid
        schedule = plan['schedule']
        new_id, ts = uid('task'), now()
        db.execute("INSERT INTO tasks (id,tenant,instruction,status,plan,version,result,created_at,updated_at,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?,?)", (new_id, tenant, original['instruction'], 'awaiting_approval', json.dumps(plan, ensure_ascii=False), 1, None, ts, ts, None))
        db.execute("INSERT INTO schedules (task_id,interval_seconds,max_runs,next_run) VALUES (?,?,?,?)", (new_id, schedule['interval_seconds'], schedule['max_runs'], ts))
        event(db, tenant, new_id, 'task.created.v1', {'rerun_of':tid})
        event(db, tenant, new_id, 'task.approval_requested.v1', {'version':1,'rerun_of':tid})
        conversation = db.execute("SELECT m.conversation_id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.task_id=? AND c.tenant=? AND c.status!='deleted' ORDER BY m.rowid DESC LIMIT 1", (tid,tenant)).fetchone()
        if conversation:
            db.execute("INSERT INTO messages (id,conversation_id,role,content,task_id,created_at) VALUES (?,?,?,?,?,?)", (uid('msg'), conversation['conversation_id'], 'assistant', 'I have prepared the task to run again. Please review and approve the plan.', new_id, ts))
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (ts, conversation['conversation_id']))
        return task_dict(db.execute("SELECT * FROM tasks WHERE id=?", (new_id,)).fetchone())


@app.patch("/v1/tasks/{tid}/schedule")
def update_schedule(tid: str, body: ScheduleUpdate, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = get_task_row(db, tid, tenant, lock=True)
        schedule = db.execute("SELECT runs FROM schedules WHERE task_id=?", (tid,)).fetchone()
        if row["archived"] or row["status"] not in ("awaiting_approval", "scheduled", "paused") or row["version"] != body.version:
            raise HTTPException(409, "The task has changed or cannot be edited")
        if body.schedule.max_runs <= schedule["runs"]:
            raise HTTPException(422, "The number of checks must be greater than the number already completed")
        plan = json.loads(row["plan"])
        plan["schedule"] = body.schedule.model_dump()
        version = row["version"] + 1
        db.execute("UPDATE tasks SET plan=?, version=?, status='awaiting_approval', updated_at=? WHERE id=?", (json.dumps(plan, ensure_ascii=False), version, now(), tid))
        db.execute("UPDATE schedules SET interval_seconds=?,max_runs=?,next_run=? WHERE task_id=?", (body.schedule.interval_seconds, body.schedule.max_runs, now(), tid))
        release_task_source_automation(db, tid)
        event(db, tenant, tid, "task.approval_requested.v1", {"version": version, "reason": "schedule_updated"})
        return task_dict(db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())


@app.delete("/v1/tasks/{tid}")
def archive_task(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = get_task_row(db, tid, tenant, lock=True)
        if row["archived"]:
            raise HTTPException(409, "The task has already been removed from the list")
        status = "cancelled" if row["status"] in ("awaiting_approval", "scheduled", "paused") else row["status"]
        if row["status"] == "running":
            raise HTTPException(409, "Task is running; try again after it finishes")
        db.execute("UPDATE tasks SET archived=1,status=?,updated_at=? WHERE id=?", (status, now(), tid))
        release_task_source_automation(db, tid)
        event(db, tenant, tid, "task.archived.v1", {"status": status})
        return {"status": status, "archived": True}


@app.get("/v1/tasks/{tid}/runs")
def task_runs(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        get_task_row(db, tid, tenant)
        return [{**dict(row), "results": json.loads(row["results"])} for row in db.execute("SELECT * FROM task_runs WHERE task_id=? ORDER BY number", (tid,))]


@app.post("/v1/tasks/{tid}/approve")
def approve(tid: str, body: Approval, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        row = get_task_row(db, tid, tenant)
        if row["status"] != "awaiting_approval" or body.version != row["version"]:
            raise HTTPException(409, "Task status or plan version does not match")
        cur = db.execute("UPDATE tasks SET status='scheduled', updated_at=? WHERE id=? AND status='awaiting_approval' AND version=?", (now(), tid, body.version))
        if not cur.rowcount:
            raise HTTPException(409, "Task telah berubah")
        event(db, tenant, tid, "task.approved.v1", {"version": body.version})
        acquire_task_source_automation(db, tid, tenant, json.loads(row['plan']))
        return task_dict(db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())


@app.post("/v1/tasks/{tid}/cancel")
def cancel(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        get_task_row(db, tid, tenant)
        cur = db.execute("UPDATE tasks SET status='cancelled', updated_at=? WHERE id=? AND status IN ('awaiting_approval','scheduled','paused') AND archived=0", (now(), tid))
        if not cur.rowcount:
            raise HTTPException(409, "Task cannot dibatalkan")
        event(db, tenant, tid, "task.cancelled.v1", {})
        release_task_source_automation(db, tid)
    return {"status": "cancelled"}


def change_pause_status(tid: str, tenant: str, before: str, after: str):
    with connect() as db:
        get_task_row(db, tid, tenant)
        cur = db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=? AND tenant=? AND status=? AND archived=0", (after, now(), tid, tenant, before))
        if not cur.rowcount:
            raise HTTPException(409, "The task status has changed or this action is unavailable")
        event(db, tenant, tid, "task.paused.v1" if after == "paused" else "task.resumed.v1", {"status": after})
        if after == "paused":
            release_task_source_automation(db, tid)
        else:
            task = db.execute("SELECT plan FROM tasks WHERE id=? AND tenant=?", (tid, tenant)).fetchone()
            acquire_task_source_automation(db, tid, tenant, json.loads(task['plan']))
        return task_dict(db.execute("SELECT * FROM tasks WHERE id=? AND tenant=?", (tid, tenant)).fetchone())


@app.post("/v1/tasks/{tid}/pause")
def pause(tid: str, tenant: str = Depends(tenant_auth)):
    return change_pause_status(tid, tenant, "scheduled", "paused")


@app.post("/v1/tasks/{tid}/resume")
def resume(tid: str, tenant: str = Depends(tenant_auth)):
    return change_pause_status(tid, tenant, "paused", "scheduled")


@app.get("/v1/events")
def events(after: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=1000), tenant: str = Depends(tenant_auth)):
    with connect() as db:
        rows = db.execute("SELECT rowid AS cursor,* FROM events WHERE tenant=? AND rowid>? ORDER BY rowid LIMIT ?", (tenant, after, limit))
        return [event_dict(r) for r in rows]


NOTIFICATION_TYPES = ('task.approval_requested.v1', 'task.completed.v1', 'task.failed.v1', 'task.escalated.v1', 'task.cancelled.v1', 'task.paused.v1', 'task.resumed.v1')


def selected_notification_types(db, tenant):
    row = db.execute('SELECT event_types FROM notification_preferences WHERE tenant=?', (tenant,)).fetchone()
    return list(NOTIFICATION_TYPES) if not row else [kind for kind in json.loads(row['event_types']) if kind in NOTIFICATION_TYPES]


@app.get('/v1/notifications/preferences')
def get_notification_preferences(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return {'event_types': selected_notification_types(db, tenant), 'available_types': list(NOTIFICATION_TYPES)}


@app.put('/v1/notifications/preferences')
def put_notification_preferences(body: EventTypePreferences, tenant: str = Depends(tenant_auth)):
    if len(set(body.event_types)) != len(body.event_types) or any(kind not in NOTIFICATION_TYPES for kind in body.event_types):
        raise HTTPException(422, 'Notification type is unknown or duplicated')
    with connect() as db:
        db.execute('INSERT INTO notification_preferences (tenant,event_types) VALUES (?,?) ON CONFLICT(tenant) DO UPDATE SET event_types=excluded.event_types', (tenant, json.dumps(body.event_types)))
    return {'event_types': body.event_types, 'available_types': list(NOTIFICATION_TYPES)}


@app.get("/v1/notifications")
def notifications(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        event_types = selected_notification_types(db, tenant)
        if not event_types:
            return []
        placeholders = ','.join('?' for _ in event_types)
        rows = db.execute(f"SELECT e.id,e.task_id,e.type,e.occurred_at,e.data,t.instruction,t.status AS task_status,t.archived,t.result AS task_result,CASE WHEN r.event_id IS NULL THEN 0 ELSE 1 END AS is_read FROM events e LEFT JOIN tasks t ON t.id=e.task_id AND t.tenant=e.tenant LEFT JOIN notification_reads r ON r.event_id=e.id AND r.tenant=e.tenant WHERE e.tenant=? AND e.type IN ({placeholders}) ORDER BY e.rowid DESC LIMIT 100", (tenant, *event_types)).fetchall()
        return [{**dict(row), 'data':json.loads(row['data']), 'task_result':json.loads(row['task_result']) if row['task_result'] else None, 'is_read':bool(row['is_read'])} for row in rows]


@app.get("/v1/notifications/unread-count")
def unread_notification_count(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        event_types = selected_notification_types(db, tenant)
        if not event_types:
            return {'count': 0}
        placeholders = ','.join('?' for _ in event_types)
        row = db.execute(f"SELECT COUNT(*) AS total FROM events e LEFT JOIN notification_reads r ON r.event_id=e.id AND r.tenant=e.tenant WHERE e.tenant=? AND e.type IN ({placeholders}) AND r.event_id IS NULL", (tenant, *event_types)).fetchone()
    return {'count': row['total']}


@app.post("/v1/notifications/read-all")
def read_all_notifications(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        event_types = selected_notification_types(db, tenant)
        if not event_types:
            return {'status': 'read'}
        placeholders = ','.join('?' for _ in event_types)
        db.execute(f"INSERT OR IGNORE INTO notification_reads (tenant,event_id,read_at) SELECT tenant,id,? FROM events WHERE tenant=? AND type IN ({placeholders})", (now(), tenant, *event_types))
    return {'status': 'read'}


@app.post("/v1/notifications/{event_id}/read")
def read_notification(event_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        row = db.execute("SELECT type FROM events WHERE id=? AND tenant=?", (event_id, tenant)).fetchone()
        if not row or row['type'] not in NOTIFICATION_TYPES:
            raise HTTPException(404, "Notifikasi not found")
        db.execute("INSERT OR IGNORE INTO notification_reads VALUES (?,?,?)", (tenant, event_id, now()))
    return {'status':'read'}


@app.post("/v1/webhook-subscriptions", status_code=201)
def create_subscription(body: SubscriptionRequest, tenant: str = Depends(tenant_auth)):
    validate_subscription_event_types(body.event_types)
    try:
        validate_url(body.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    sid, secret, ts = uid("sub"), secrets.token_urlsafe(32), now()
    with connect() as db:
        db.execute("INSERT INTO subscriptions (id,tenant,url,secret,active,created_at,event_types) VALUES (?,?,?,?,?,?,?)", (sid, tenant, body.url, secret, 1, ts, json.dumps(body.event_types)))
    return {"id": sid, "url": body.url, "secret": secret, "event_types": body.event_types, "created_at": ts}


@app.get("/v1/webhook-subscriptions")
def subscriptions(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [{**dict(row), 'event_types': json.loads(row['event_types'])} for row in db.execute("SELECT id,url,active,created_at,event_types FROM subscriptions WHERE tenant=?", (tenant,))]


def validate_subscription_event_types(event_types):
    if (len(set(event_types)) != len(event_types)
            or any(not isinstance(kind, str) or not re.fullmatch(r'[A-Za-z0-9._*-]{1,100}', kind) for kind in event_types)
            or ('*' in event_types and event_types != ['*'])):
        raise HTTPException(422, 'Filter event webhook invalid')


@app.put('/v1/webhook-subscriptions/{sid}/event-types')
def update_subscription_event_types(sid: str, body: SubscriptionEventTypes, tenant: str = Depends(tenant_auth)):
    validate_subscription_event_types(body.event_types)
    with connect() as db:
        cur = db.execute('UPDATE subscriptions SET event_types=? WHERE id=? AND tenant=?', (json.dumps(body.event_types), sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, 'Subscription not found')
    return {'id': sid, 'event_types': body.event_types}


@app.delete("/v1/webhook-subscriptions/{sid}")
def delete_subscription(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE subscriptions SET active=0 WHERE id=? AND tenant=?", (sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Subscription not found")
    return {"status": "disabled"}


@app.get("/v1/webhook-deliveries")
def deliveries(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT d.id,d.subscription_id,d.event_id,d.status,d.attempts,d.next_attempt,d.last_status FROM deliveries d JOIN subscriptions s ON d.subscription_id=s.id WHERE s.tenant=? ORDER BY d.rowid DESC LIMIT 100", (tenant,))]


@app.get('/v1/events/export')
def export_events(format: str = Query(default='json', pattern='^(json|csv)$'), limit: int = Query(default=500, ge=1, le=1000), after: int = Query(default=0, ge=0), tenant: str = Depends(tenant_auth)):
    with connect() as db:
        rows = [event_dict(row) for row in db.execute('SELECT rowid AS cursor,* FROM events WHERE tenant=? AND rowid>? ORDER BY rowid LIMIT ?', (tenant, after, limit))]
    fields = ['cursor','id','tenant','task_id','type','occurred_at','data']
    return export_rows(rows, fields, format, 'kanca-events')


@app.get("/v1/tasks/{tid}/events")
def task_events(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        get_task_row(db, tid, tenant)
        return [event_dict(r) for r in db.execute("SELECT * FROM events WHERE tenant=? AND task_id=? ORDER BY occurred_at,id", (tenant, tid))]
