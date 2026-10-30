import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.connectors.registry import CAPABILITIES, describe
from app.planner import PlanningError, propose
from app.service import validate_steps
from app.storage import connect, event, event_dict, initialize, now, task_dict, uid
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

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (FRONTEND_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


def session_token(key: str) -> str:
    return hmac.new(key.encode(), b"kanca-local-ui-session-v1", hashlib.sha256).hexdigest()


def tenant_auth(request: Request, x_api_key: str = Header(default="")) -> str:
    key = os.getenv("KANCA_API_KEY", "")
    via_header = bool(key and hmac.compare_digest(hashlib.sha256(x_api_key.encode()).digest(), hashlib.sha256(key.encode()).digest()))
    via_cookie = bool(key and hmac.compare_digest(request.cookies.get("kanca_session", ""), session_token(key)))
    if not via_header and not via_cookie:
        raise HTTPException(401, "API key tidak valid atau belum dikonfigurasi")
    if via_cookie and not via_header and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Origin tidak valid")
    # This initial deployment has exactly one configured tenant.
    return "default"


class ConnectionRequest(BaseModel):
    type: str


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


class ConversationRequest(BaseModel):
    title: str = Field(default="Percakapan baru", min_length=1, max_length=100)


class ConversationUpdate(BaseModel):
    status: str = Field(pattern="^(active|draft)$")


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SourceInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=50)


class SourceUpdate(SourceInput):
    status: str = Field(pattern="^(active|disabled)$")


class MediaSettings(BaseModel):
    vision_enabled: bool = False
    audio_enabled: bool = False
    vision_prompt: str = Field(default='Jelaskan kondisi operasional yang terlihat.', min_length=1, max_length=500)
    audio_prompt: str = Field(default='Rangkum suara yang terdengar.', min_length=1, max_length=500)


media_slots = asyncio.Semaphore(2)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    index = FRONTEND_DIR / "index.html"
    if not index.is_file():
        return JSONResponse({"detail": "Frontend belum dibangun. Jalankan npm install && npm run build di folder frontend."}, status_code=503)
    return FileResponse(index)


@app.get("/v1/session", include_in_schema=False)
def ui_session():
    response = JSONResponse({"status": "ok"} if os.getenv("KANCA_API_KEY") else {"detail": "KANCA_API_KEY belum dikonfigurasi"}, status_code=200 if os.getenv("KANCA_API_KEY") else 503)
    key = os.getenv("KANCA_API_KEY", "")
    if key:
        response.set_cookie("kanca_session", session_token(key), httponly=True, samesite="strict", path="/")
    return response


@app.get("/v1/connector-types")
def connector_types(tenant: str = Depends(tenant_auth)):
    return [{"type": "business_demo", "mode": "simulated"}, {"type": "device_demo", "mode": "simulated"}]


@app.post("/v1/sources", status_code=201)
def create_source(body: SourceInput, tenant: str = Depends(tenant_auth)):
    name, kind = body.name.strip(), body.kind.strip()
    if not name or not kind:
        raise HTTPException(422, "Nama dan jenis sumber wajib diisi")
    sid, token, ts = uid("src"), secrets.token_urlsafe(32), now()
    with connect() as db:
        db.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?)", (sid, tenant, name, kind, hashlib.sha256(token.encode()).hexdigest(), "active", ts, None))
    return {"id": sid, "name": name, "kind": kind, "status": "active", "created_at": ts, "token": token, "ingest_path": f"/v1/ingest/{sid}"}


@app.get("/v1/sources")
def list_sources(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT id,name,kind,status,created_at,last_seen FROM sources WHERE tenant=? AND status!='deleted' ORDER BY created_at DESC", (tenant,))]


@app.put("/v1/sources/{sid}")
def update_source(sid: str, body: SourceUpdate, tenant: str = Depends(tenant_auth)):
    name, kind = body.name.strip(), body.kind.strip()
    if not name or not kind:
        raise HTTPException(422, "Nama dan jenis sumber wajib diisi")
    with connect() as db:
        cur = db.execute("UPDATE sources SET name=?,kind=?,status=? WHERE id=? AND tenant=? AND status!='deleted'", (name, kind, body.status, sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Sumber tidak ditemukan")
    return {"id": sid, "name": name, "kind": kind, "status": body.status}


@app.delete("/v1/sources/{sid}")
def delete_source(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE sources SET status='deleted' WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Sumber tidak ditemukan")
    return {"status": "deleted"}


@app.get("/v1/sources/{sid}/events")
def source_events(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        if not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=?", (sid, tenant)).fetchone():
            raise HTTPException(404, "Sumber tidak ditemukan")
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in db.execute("SELECT * FROM source_events WHERE source_id=? ORDER BY rowid DESC LIMIT 50", (sid,))]


@app.get("/v1/sources/{sid}/media-settings")
def get_media_settings(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        if not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant)).fetchone():
            raise HTTPException(404, "Sumber tidak ditemukan")
        row = db.execute("SELECT vision_enabled,audio_enabled,vision_prompt,audio_prompt FROM source_media_settings WHERE source_id=?", (sid,)).fetchone()
        if not row:
            return MediaSettings().model_dump()
        return {**dict(row), 'vision_enabled':bool(row['vision_enabled']), 'audio_enabled':bool(row['audio_enabled'])}


@app.put("/v1/sources/{sid}/media-settings")
def put_media_settings(sid: str, body: MediaSettings, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        if not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=? AND status!='deleted'", (sid, tenant)).fetchone():
            raise HTTPException(404, "Sumber tidak ditemukan")
        db.execute("INSERT INTO source_media_settings VALUES (?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET vision_enabled=excluded.vision_enabled,audio_enabled=excluded.audio_enabled,vision_prompt=excluded.vision_prompt,audio_prompt=excluded.audio_prompt", (sid, int(body.vision_enabled), int(body.audio_enabled), body.vision_prompt, body.audio_prompt))
    return body.model_dump()


@app.post("/v1/ingest/{sid}/media", status_code=202)
async def ingest_media(sid: str, request: Request, media_type: str = Query(pattern='^(vision|audio)$'), authorization: str = Header(default="")):
    supplied = authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else ''
    token_hash = hashlib.sha256(supplied.encode()).hexdigest()
    def authorized(db, lock=False):
        query = "SELECT s.tenant,s.token_hash,m.vision_enabled,m.audio_enabled,m.vision_prompt,m.audio_prompt FROM sources s JOIN source_media_settings m ON m.source_id=s.id WHERE s.id=? AND s.status='active'"
        if lock and getattr(db, 'is_postgres', False): query += ' FOR UPDATE OF s,m'
        row = db.execute(query, (sid,)).fetchone()
        if not row or not supplied or not hmac.compare_digest(token_hash, row['token_hash']):
            raise HTTPException(401, 'Kredensial sumber tidak valid atau media belum diaktifkan')
        if not row[media_type + '_enabled']:
            raise HTTPException(403, 'Analisis media belum diaktifkan untuk sumber ini')
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
    try:
        async with media_slots:
            result = await media.analyze(media_type, raw, mime, prompt)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = authorized(db, lock=True)
        if current[media_type + '_prompt'] != prompt:
            raise HTTPException(409, 'Pengaturan analisis berubah; hasil tidak disimpan')
        eid, ts = uid('sevt'), now()
        db.execute('INSERT INTO source_events (id,source_id,event_type,payload,received_at) VALUES (?,?,?,?,?)', (eid, sid, 'media.' + media_type, json.dumps(result, ensure_ascii=False), ts))
        db.execute('UPDATE sources SET last_seen=? WHERE id=?', (ts, sid))
        event(db, tenant, '', 'source.event.v1', {'source_id':sid, 'source_event_id':eid, 'type':'media.' + media_type})
    return {'id':eid, 'status':'received', 'result':result}


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
        payload = json.loads(b"".join(chunks), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON constant")))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(422, "Data harus berupa JSON")
    if not isinstance(payload, dict) or not isinstance(payload.get("type"), str) or not 1 <= len(payload["type"]) <= 100 or not isinstance(payload.get("data"), dict):
        raise HTTPException(422, "Kirim objek dengan type dan data")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        source_query = "SELECT * FROM sources WHERE id=? AND status='active'"
        if getattr(db, 'is_postgres', False): source_query += ' FOR UPDATE'
        source = db.execute(source_query, (sid,)).fetchone()
        if not source or not supplied or not hmac.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(), source["token_hash"]):
            raise HTTPException(401, "Kredensial sumber tidak valid")
        eid, ts = uid("sevt"), now()
        db.execute("INSERT INTO source_events (id,source_id,event_type,payload,received_at) VALUES (?,?,?,?,?)", (eid, sid, payload["type"], json.dumps(payload["data"], ensure_ascii=False), ts))
        db.execute("UPDATE sources SET last_seen=? WHERE id=?", (ts, sid))
        event(db, source["tenant"], "", "source.event.v1", {"source_id": sid, "source_event_id": eid, "type": payload["type"]})
    return {"id": eid, "status": "received"}


@app.post("/v1/connections", status_code=201)
def create_connection(body: ConnectionRequest, tenant: str = Depends(tenant_auth)):
    if body.type not in {"business_demo", "device_demo"}:
        raise HTTPException(400, "Connector tidak tersedia")
    item = {"id": uid("conn"), "type": body.type, "status": "connected", "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO connections VALUES (?,?,?,?,?)", (item["id"], tenant, item["type"], item["status"], item["created_at"]))
    return item


@app.get("/v1/connections")
def connections(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id,type,status,created_at FROM connections WHERE tenant=?", (tenant,))]


@app.delete("/v1/connections/{connection_id}")
def revoke(connection_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE connections SET status='revoked' WHERE id=? AND tenant=?", (connection_id, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Connection tidak ditemukan")
    return {"status": "revoked"}


@app.get("/v1/connections/{connection_id}/resources")
def resources(connection_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        row = db.execute("SELECT type,status FROM connections WHERE id=? AND tenant=?", (connection_id, tenant)).fetchone()
    if not row:
        raise HTTPException(404, "Connection tidak ditemukan")
    return {"connection_id": connection_id, "status": row["status"], "capabilities": describe(row["type"]) if row["status"] == "connected" else []}


@app.post("/v1/tasks", status_code=201)
def create_task(body: TaskRequest, idempotency_key: str | None = Header(default=None, max_length=200), tenant: str = Depends(tenant_auth)):
    return create_task_internal(body, idempotency_key, tenant)


def connected_capabilities(db, tenant):
    connected = {r[0] for r in db.execute("SELECT type FROM connections WHERE tenant=? AND status='connected'", (tenant,))}
    sources = db.execute("SELECT id,name,kind FROM sources WHERE tenant=? AND status='active'", (tenant,)).fetchall()
    if sources:
        connected.add("external_events")
    available = [item for item in describe() if item["connector"] in connected]
    for item in available:
        if item["name"] == "external.latest_event":
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
                    raise HTTPException(409, "Idempotency-Key telah dipakai untuk request lain")
                return task_dict(existing)
        connected, available = connected_capabilities(db, tenant)
        if body.explicit_steps is not None and proposed is None:
            plan = {"summary": "Rencana eksplisit dari pengguna (mode demo).", "steps": [s.model_dump(exclude_none=True) for s in body.explicit_steps], "source": "explicit"}
        else:
            try:
                plan = proposed if proposed is not None else propose(body.instruction, available)
            except PlanningError as exc:
                raise HTTPException(503, str(exc)) from exc
            if not isinstance(plan, dict):
                raise HTTPException(422, "Model mengembalikan rencana yang tidak valid")
            if not plan.get("steps"):
                raise HTTPException(422, {"clarification": plan.get("clarification") or "Instruksi tidak dapat direncanakan dengan capability yang tersedia."})
            try:
                model_schedule = Schedule.model_validate(plan.get("schedule") or {"interval_seconds": 1, "max_runs": 1})
            except ValueError as exc:
                raise HTTPException(422, "Jadwal dari model tidak valid") from exc
            plan = {"summary": str(plan.get("summary", "Rencana agent")), "steps": plan["steps"], "source": "baseten", "schedule": model_schedule.model_dump()}
        try:
            validate_steps(plan["steps"], connected)
            for step in plan["steps"]:
                if step["capability"] == "external.latest_event" and not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=? AND status='active'", (step["arguments"]["source_id"], tenant)).fetchone():
                    raise ValueError("Sumber yang diminta tidak aktif atau tidak tersedia.")
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
            else:
                event(db, tenant, tid, "task.approval_requested.v1", {"version": 1})
        except INTEGRITY_ERRORS:
            db.rollback()
            if idempotency_key:
                existing = db.execute("SELECT * FROM tasks WHERE tenant=? AND idempotency_key=?", (tenant, idempotency_key)).fetchone()
                if existing:
                    if json.loads(existing["plan"]).get("request_hash") != plan["request_hash"]:
                        raise HTTPException(409, "Idempotency-Key telah dipakai untuk request lain")
                    return task_dict(existing)
            raise
        row = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    return task_dict(row)


def get_conversation(db, cid, tenant):
    row = db.execute("SELECT * FROM conversations WHERE id=? AND tenant=? AND status!='deleted'", (cid, tenant)).fetchone()
    if row is None:
        raise HTTPException(404, "Percakapan tidak ditemukan")
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
            raise HTTPException(404, "Percakapan tidak ditemukan")
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


@app.post("/v1/conversations/{cid}/messages", status_code=201)
def send_message(cid: str, body: MessageRequest, tenant: str = Depends(tenant_auth)):
    content = body.content.strip()
    if not content:
        raise HTTPException(422, "Pesan tidak boleh kosong")
    with connect() as db:
        conversation = get_conversation(db, cid, tenant)
        rows = db.execute("SELECT role,content FROM messages WHERE conversation_id=? ORDER BY rowid DESC LIMIT 12", (cid,)).fetchall()
        history = [dict(row) for row in reversed(rows)]
        connected, available = connected_capabilities(db, tenant)
        ts = now()
        db.execute("INSERT INTO messages (id,conversation_id,role,content,task_id,created_at) VALUES (?,?,?,?,?,?)", (uid("msg"), cid, "user", content, None, ts))
        title = content[:70] if conversation["title"] == "Percakapan baru" else conversation["title"]
        db.execute("UPDATE conversations SET title=?,updated_at=? WHERE id=?", (title, ts, cid))
    try:
        plan = propose(content, available, history)
        for attempt in range(2):
            if not isinstance(plan, dict):
                raise ValueError("Model mengembalikan respons yang tidak valid.")
            if not plan.get("steps"):
                answer = str(plan.get("answer") or plan.get("clarification") or "Bisa ceritakan sedikit lebih detail apa yang kamu butuhkan?")
                task_id = None
                break
            try:
                task = create_task_internal(TaskRequest(instruction=content), None, tenant, proposed=plan, auto_approve_safe=True)
            except HTTPException as exc:
                if exc.status_code != 422 or attempt:
                    raise
                plan = propose(content, available, history, feedback=f"Rencana sebelumnya ditolak: {exc.detail}. Perbaiki format dengan data yang tersedia atau minta klarifikasi.")
                continue
            answer = "Oke, aku akan mengerjakannya. Hasilnya akan muncul di sini." if task['status'] == 'scheduled' else "Aku sudah menyiapkan rencana. Silakan periksa dan setujui sebelum aku mulai."
            task_id = task["id"]
            break
    except PlanningError as exc:
        answer, task_id = "Maaf, aku belum bisa menjawab sekarang. Coba lagi sebentar lagi, ya.", None
    except (ValueError, HTTPException) as exc:
        answer, task_id = "Maaf, aku belum bisa membuat rencana yang cocok dengan perangkat yang terhubung. Pastikan sumber yang diperlukan sudah terhubung, lalu coba lagi dengan waktu dan kondisi yang jelas.", None
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
        raise HTTPException(404, "Task tidak ditemukan")
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
            raise HTTPException(409, "Hanya tugas selesai, gagal, atau dihentikan yang dapat dibuat ulang")
        plan = json.loads(original['plan'])
        connected, _ = connected_capabilities(db, tenant)
        try:
            validate_steps(plan['steps'], connected)
            for step in plan['steps']:
                if step['capability'] == 'external.latest_event' and not db.execute("SELECT 1 FROM sources WHERE id=? AND tenant=? AND status='active'", (step['arguments']['source_id'], tenant)).fetchone():
                    raise ValueError("Sumber tidak aktif atau tidak tersedia")
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
            db.execute("INSERT INTO messages (id,conversation_id,role,content,task_id,created_at) VALUES (?,?,?,?,?,?)", (uid('msg'), conversation['conversation_id'], 'assistant', 'Aku sudah menyiapkan tugas untuk dijalankan ulang. Silakan periksa dan setujui rencananya.', new_id, ts))
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (ts, conversation['conversation_id']))
        return task_dict(db.execute("SELECT * FROM tasks WHERE id=?", (new_id,)).fetchone())


@app.patch("/v1/tasks/{tid}/schedule")
def update_schedule(tid: str, body: ScheduleUpdate, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = get_task_row(db, tid, tenant, lock=True)
        schedule = db.execute("SELECT runs FROM schedules WHERE task_id=?", (tid,)).fetchone()
        if row["archived"] or row["status"] not in ("awaiting_approval", "scheduled", "paused") or row["version"] != body.version:
            raise HTTPException(409, "Tugas sudah berubah atau tidak dapat diubah")
        if body.schedule.max_runs <= schedule["runs"]:
            raise HTTPException(422, "Jumlah pemeriksaan harus lebih besar dari yang sudah dilakukan")
        plan = json.loads(row["plan"])
        plan["schedule"] = body.schedule.model_dump()
        version = row["version"] + 1
        db.execute("UPDATE tasks SET plan=?, version=?, status='awaiting_approval', updated_at=? WHERE id=?", (json.dumps(plan, ensure_ascii=False), version, now(), tid))
        db.execute("UPDATE schedules SET interval_seconds=?,max_runs=?,next_run=? WHERE task_id=?", (body.schedule.interval_seconds, body.schedule.max_runs, now(), tid))
        event(db, tenant, tid, "task.approval_requested.v1", {"version": version, "reason": "schedule_updated"})
        return task_dict(db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())


@app.delete("/v1/tasks/{tid}")
def archive_task(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = get_task_row(db, tid, tenant, lock=True)
        if row["archived"]:
            raise HTTPException(409, "Tugas sudah dihapus dari daftar")
        status = "cancelled" if row["status"] in ("awaiting_approval", "scheduled", "paused") else row["status"]
        if row["status"] == "running":
            raise HTTPException(409, "Tugas sedang berjalan; coba lagi setelah selesai")
        db.execute("UPDATE tasks SET archived=1,status=?,updated_at=? WHERE id=?", (status, now(), tid))
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
            raise HTTPException(409, "Status atau versi rencana tidak sesuai")
        cur = db.execute("UPDATE tasks SET status='scheduled', updated_at=? WHERE id=? AND status='awaiting_approval' AND version=?", (now(), tid, body.version))
        if not cur.rowcount:
            raise HTTPException(409, "Task telah berubah")
        event(db, tenant, tid, "task.approved.v1", {"version": body.version})
        return task_dict(db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())


@app.post("/v1/tasks/{tid}/cancel")
def cancel(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        get_task_row(db, tid, tenant)
        cur = db.execute("UPDATE tasks SET status='cancelled', updated_at=? WHERE id=? AND status IN ('awaiting_approval','scheduled','paused') AND archived=0", (now(), tid))
        if not cur.rowcount:
            raise HTTPException(409, "Task tidak dapat dibatalkan")
        event(db, tenant, tid, "task.cancelled.v1", {})
    return {"status": "cancelled"}


def change_pause_status(tid: str, tenant: str, before: str, after: str):
    with connect() as db:
        get_task_row(db, tid, tenant)
        cur = db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=? AND tenant=? AND status=? AND archived=0", (after, now(), tid, tenant, before))
        if not cur.rowcount:
            raise HTTPException(409, "Status tugas sudah berubah atau tindakan ini tidak tersedia")
        event(db, tenant, tid, "task.paused.v1" if after == "paused" else "task.resumed.v1", {"status": after})
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


@app.get("/v1/notifications")
def notifications(tenant: str = Depends(tenant_auth)):
    placeholders = ','.join('?' for _ in NOTIFICATION_TYPES)
    with connect() as db:
        rows = db.execute(f"SELECT e.id,e.task_id,e.type,e.occurred_at,e.data,t.instruction,t.status AS task_status,t.archived,t.result AS task_result,CASE WHEN r.event_id IS NULL THEN 0 ELSE 1 END AS is_read FROM events e LEFT JOIN tasks t ON t.id=e.task_id AND t.tenant=e.tenant LEFT JOIN notification_reads r ON r.event_id=e.id AND r.tenant=e.tenant WHERE e.tenant=? AND e.type IN ({placeholders}) ORDER BY e.rowid DESC LIMIT 100", (tenant, *NOTIFICATION_TYPES)).fetchall()
        return [{**dict(row), 'data':json.loads(row['data']), 'task_result':json.loads(row['task_result']) if row['task_result'] else None, 'is_read':bool(row['is_read'])} for row in rows]


@app.get("/v1/notifications/unread-count")
def unread_notification_count(tenant: str = Depends(tenant_auth)):
    placeholders = ','.join('?' for _ in NOTIFICATION_TYPES)
    with connect() as db:
        row = db.execute(f"SELECT COUNT(*) AS total FROM events e LEFT JOIN notification_reads r ON r.event_id=e.id AND r.tenant=e.tenant WHERE e.tenant=? AND e.type IN ({placeholders}) AND r.event_id IS NULL", (tenant, *NOTIFICATION_TYPES)).fetchone()
    return {'count': row['total']}


@app.post("/v1/notifications/read-all")
def read_all_notifications(tenant: str = Depends(tenant_auth)):
    placeholders = ','.join('?' for _ in NOTIFICATION_TYPES)
    with connect() as db:
        db.execute(f"INSERT OR IGNORE INTO notification_reads (tenant,event_id,read_at) SELECT tenant,id,? FROM events WHERE tenant=? AND type IN ({placeholders})", (now(), tenant, *NOTIFICATION_TYPES))
    return {'status': 'read'}


@app.post("/v1/notifications/{event_id}/read")
def read_notification(event_id: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        row = db.execute("SELECT type FROM events WHERE id=? AND tenant=?", (event_id, tenant)).fetchone()
        if not row or row['type'] not in NOTIFICATION_TYPES:
            raise HTTPException(404, "Notifikasi tidak ditemukan")
        db.execute("INSERT OR IGNORE INTO notification_reads VALUES (?,?,?)", (tenant, event_id, now()))
    return {'status':'read'}


@app.post("/v1/webhook-subscriptions", status_code=201)
def create_subscription(body: SubscriptionRequest, tenant: str = Depends(tenant_auth)):
    try:
        validate_url(body.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    sid, secret, ts = uid("sub"), secrets.token_urlsafe(32), now()
    with connect() as db:
        db.execute("INSERT INTO subscriptions VALUES (?,?,?,?,?,?)", (sid, tenant, body.url, secret, 1, ts))
    return {"id": sid, "url": body.url, "secret": secret, "created_at": ts}


@app.get("/v1/webhook-subscriptions")
def subscriptions(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT id,url,active,created_at FROM subscriptions WHERE tenant=?", (tenant,))]


@app.delete("/v1/webhook-subscriptions/{sid}")
def delete_subscription(sid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        cur = db.execute("UPDATE subscriptions SET active=0 WHERE id=? AND tenant=?", (sid, tenant))
        if not cur.rowcount:
            raise HTTPException(404, "Subscription tidak ditemukan")
    return {"status": "disabled"}


@app.get("/v1/webhook-deliveries")
def deliveries(tenant: str = Depends(tenant_auth)):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT d.id,d.subscription_id,d.event_id,d.status,d.attempts,d.next_attempt,d.last_status FROM deliveries d JOIN subscriptions s ON d.subscription_id=s.id WHERE s.tenant=? ORDER BY d.rowid DESC LIMIT 100", (tenant,))]


@app.get("/v1/tasks/{tid}/events")
def task_events(tid: str, tenant: str = Depends(tenant_auth)):
    with connect() as db:
        get_task_row(db, tid, tenant)
        return [event_dict(r) for r in db.execute("SELECT * FROM events WHERE tenant=? AND task_id=? ORDER BY occurred_at,id", (tenant, tid))]
