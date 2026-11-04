import json
import os
import sqlite3
import uuid
import re
from datetime import datetime, timedelta, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class DatabaseRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _postgres_row(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: DatabaseRow(zip(names, values))


class PostgresConnection:
    """DB-API adapter for the existing parameterized queries."""
    is_postgres = True

    def __init__(self, url):
        import psycopg
        self.connection = psycopg.connect(url, row_factory=_postgres_row)

    def execute(self, sql, params=()):
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            return self.connection.execute('SELECT pg_advisory_xact_lock(76413102)')
        sql = re.sub(r'\browid\b', 'seq', sql, flags=re.IGNORECASE)
        if re.match(r'\s*INSERT\s+OR\s+IGNORE\s+INTO\b', sql, flags=re.IGNORECASE):
            sql = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql, count=1, flags=re.IGNORECASE)
            sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
        return self.connection.execute(sql.replace('?', '%s'), params)

    def commit(self): self.connection.commit()
    def rollback(self): self.connection.rollback()
    def close(self): self.connection.close()
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, traceback):
        try:
            self.connection.commit() if exc_type is None else self.connection.rollback()
        finally:
            self.connection.close()


def connect():
    url = os.getenv('DATABASE_URL', '')
    if url:
        if not url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('DATABASE_URL must be URL PostgreSQL')
        return PostgresConnection(url)
    path = os.getenv("KANCA_DB_PATH", "data/kanca.db")
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    return db


def initialize():
    with connect() as db:
        schema = """
        CREATE TABLE IF NOT EXISTS connections (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, name TEXT, config TEXT NOT NULL DEFAULT '{}', credentials_enc TEXT);
        CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, instruction TEXT NOT NULL, status TEXT NOT NULL, plan TEXT NOT NULL, version INTEGER NOT NULL, result TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, idempotency_key TEXT, UNIQUE(tenant,idempotency_key));
        CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, task_id TEXT NOT NULL, type TEXT NOT NULL, occurred_at TEXT NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_tenant ON events(tenant, occurred_at);
        CREATE TABLE IF NOT EXISTS steps (task_id TEXT NOT NULL, position INTEGER NOT NULL, result TEXT NOT NULL, PRIMARY KEY(task_id, position));
        CREATE TABLE IF NOT EXISTS schedules (task_id TEXT PRIMARY KEY, interval_seconds INTEGER NOT NULL, max_runs INTEGER NOT NULL, runs INTEGER NOT NULL DEFAULT 0, next_run TEXT NOT NULL, source_retry_count INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(task_id) REFERENCES tasks(id));
        CREATE TABLE IF NOT EXISTS task_runs (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, number INTEGER NOT NULL, results TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(task_id, number));
        CREATE TABLE IF NOT EXISTS subscriptions (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, url TEXT NOT NULL, secret TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL, event_id TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt TEXT NOT NULL, last_status INTEGER, UNIQUE(subscription_id,event_id), FOREIGN KEY(subscription_id) REFERENCES subscriptions(id), FOREIGN KEY(event_id) REFERENCES events(id));
        CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, task_id TEXT, created_at TEXT NOT NULL, FOREIGN KEY(conversation_id) REFERENCES conversations(id));
        CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, token_hash TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, last_seen TEXT, expected_interval_seconds INTEGER NOT NULL DEFAULT 300, automation_enabled INTEGER NOT NULL DEFAULT 0, automation_interval_seconds INTEGER NOT NULL DEFAULT 30);
        CREATE TABLE IF NOT EXISTS source_events (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL, received_at TEXT NOT NULL, FOREIGN KEY(source_id) REFERENCES sources(id));
        CREATE TABLE IF NOT EXISTS notification_reads (tenant TEXT NOT NULL, event_id TEXT NOT NULL, read_at TEXT NOT NULL, PRIMARY KEY(tenant,event_id), FOREIGN KEY(event_id) REFERENCES events(id));
        CREATE TABLE IF NOT EXISTS source_media_settings (source_id TEXT PRIMARY KEY, vision_enabled INTEGER NOT NULL DEFAULT 0, audio_enabled INTEGER NOT NULL DEFAULT 0, vision_prompt TEXT NOT NULL, audio_prompt TEXT NOT NULL, FOREIGN KEY(source_id) REFERENCES sources(id));
        CREATE TABLE IF NOT EXISTS source_automation_lease_state (source_id TEXT PRIMARY KEY, previous_enabled INTEGER NOT NULL, previous_interval_seconds INTEGER NOT NULL, previous_vision_enabled INTEGER, previous_audio_enabled INTEGER, previous_vision_prompt TEXT, FOREIGN KEY(source_id) REFERENCES sources(id));
        CREATE TABLE IF NOT EXISTS task_source_automation_leases (task_id TEXT NOT NULL, source_id TEXT NOT NULL, PRIMARY KEY(task_id,source_id), FOREIGN KEY(task_id) REFERENCES tasks(id), FOREIGN KEY(source_id) REFERENCES sources(id));
        CREATE TABLE IF NOT EXISTS notification_preferences (tenant TEXT PRIMARY KEY, event_types TEXT NOT NULL);
        """
        if getattr(db, 'is_postgres', False):
            db.execute('SELECT pg_advisory_xact_lock(76413101)')
            for statement in schema.split(';'):
                if statement.strip(): db.execute(statement)
            for table in ('events', 'messages', 'conversations', 'source_events', 'deliveries'):
                exists = db.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? AND column_name='seq'", (table,)).fetchone()
                if not exists:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN seq BIGSERIAL UNIQUE')
            db.execute('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS archived INTEGER NOT NULL DEFAULT 0')
            db.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'")
            db.execute("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS event_types TEXT NOT NULL DEFAULT '[\"*\"]'")
            db.execute('ALTER TABLE sources ADD COLUMN IF NOT EXISTS expected_interval_seconds INTEGER NOT NULL DEFAULT 300')
            db.execute('ALTER TABLE sources ADD COLUMN IF NOT EXISTS automation_enabled INTEGER NOT NULL DEFAULT 0')
            db.execute('ALTER TABLE sources ADD COLUMN IF NOT EXISTS automation_interval_seconds INTEGER NOT NULL DEFAULT 30')
            db.execute('ALTER TABLE source_automation_lease_state ADD COLUMN IF NOT EXISTS previous_vision_prompt TEXT')
            db.execute('ALTER TABLE schedules ADD COLUMN IF NOT EXISTS source_retry_count INTEGER NOT NULL DEFAULT 0')
            db.execute('ALTER TABLE connections ADD COLUMN IF NOT EXISTS name TEXT')
            db.execute("ALTER TABLE connections ADD COLUMN IF NOT EXISTS config TEXT NOT NULL DEFAULT '{}'")
            db.execute('ALTER TABLE connections ADD COLUMN IF NOT EXISTS credentials_enc TEXT')
        else:
            db.executescript(schema)
            if "archived" not in {row[1] for row in db.execute("PRAGMA table_info(tasks)")}:
                db.execute("ALTER TABLE tasks ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
            if "status" not in {row[1] for row in db.execute("PRAGMA table_info(conversations)")}:
                db.execute("ALTER TABLE conversations ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
            if "event_types" not in {row[1] for row in db.execute("PRAGMA table_info(subscriptions)")}:
                db.execute("ALTER TABLE subscriptions ADD COLUMN event_types TEXT NOT NULL DEFAULT '[\"*\"]'")
            if "expected_interval_seconds" not in {row[1] for row in db.execute("PRAGMA table_info(sources)")}:
                db.execute('ALTER TABLE sources ADD COLUMN expected_interval_seconds INTEGER NOT NULL DEFAULT 300')
            if "automation_enabled" not in {row[1] for row in db.execute("PRAGMA table_info(sources)")}:
                db.execute('ALTER TABLE sources ADD COLUMN automation_enabled INTEGER NOT NULL DEFAULT 0')
            if "automation_interval_seconds" not in {row[1] for row in db.execute("PRAGMA table_info(sources)")}:
                db.execute('ALTER TABLE sources ADD COLUMN automation_interval_seconds INTEGER NOT NULL DEFAULT 30')
            if "previous_vision_prompt" not in {row[1] for row in db.execute("PRAGMA table_info(source_automation_lease_state)")}:
                db.execute('ALTER TABLE source_automation_lease_state ADD COLUMN previous_vision_prompt TEXT')
            if "source_retry_count" not in {row[1] for row in db.execute("PRAGMA table_info(schedules)")}:
                db.execute('ALTER TABLE schedules ADD COLUMN source_retry_count INTEGER NOT NULL DEFAULT 0')
            connection_columns = {row[1] for row in db.execute("PRAGMA table_info(connections)")}
            if "name" not in connection_columns:
                db.execute('ALTER TABLE connections ADD COLUMN name TEXT')
            if "config" not in connection_columns:
                db.execute("ALTER TABLE connections ADD COLUMN config TEXT NOT NULL DEFAULT '{}'")
            if "credentials_enc" not in connection_columns:
                db.execute('ALTER TABLE connections ADD COLUMN credentials_enc TEXT')
        db.execute("INSERT OR IGNORE INTO schedules (task_id,interval_seconds,max_runs,next_run) SELECT id,1,1,created_at FROM tasks")


def acquire_task_source_automation(db, task_id: str, tenant: str, plan: dict) -> None:
    """Keep recurring source tasks fed while they run; restore source settings at release."""
    schedule = plan.get('schedule') or {}
    if schedule.get('max_runs', 1) <= 1:
        return
    source_ids = list(dict.fromkeys(
        step.get('arguments', {}).get('source_id')
        for step in plan.get('steps', [])
        if step.get('capability') in ('external.latest_event', 'erp.demo.reconcile_source_receipt')
    ))
    source_ids = [source_id for source_id in source_ids if isinstance(source_id, str)]
    if not source_ids:
        return
    camera_prompt = ('Estimate the number of clearly visible cartons, boxes, or package-like items and describe visible arrivals or departures. '
                     'State uncertainty, do not infer hidden stock, and set count to null when the view is unclear.')
    for source_id in source_ids:
        source = db.execute(
            "SELECT kind,automation_enabled,automation_interval_seconds FROM sources WHERE id=? AND tenant=? AND status='active'",
            (source_id, tenant),
        ).fetchone()
        if not source or source['kind'] not in ('camera', 'iot'):
            continue
        media_settings = db.execute(
            'SELECT vision_enabled,audio_enabled,vision_prompt FROM source_media_settings WHERE source_id=?', (source_id,)
        ).fetchone() if source['kind'] == 'camera' else None
        db.execute(
            'INSERT OR IGNORE INTO source_automation_lease_state (source_id,previous_enabled,previous_interval_seconds,previous_vision_enabled,previous_audio_enabled,previous_vision_prompt) VALUES (?,?,?,?,?,?)',
            (source_id, source['automation_enabled'], source['automation_interval_seconds'],
             media_settings['vision_enabled'] if media_settings else None,
             media_settings['audio_enabled'] if media_settings else None,
             media_settings['vision_prompt'] if media_settings else None),
        )
        db.execute('INSERT OR IGNORE INTO task_source_automation_leases (task_id,source_id) VALUES (?,?)', (task_id, source_id))
        # A 30-second read keeps the five-minute task freshness window from expiring.
        db.execute('UPDATE sources SET automation_enabled=1,automation_interval_seconds=30 WHERE id=?', (source_id,))
        if source['kind'] == 'camera':
            db.execute(
                'INSERT INTO source_media_settings (source_id,vision_enabled,audio_enabled,vision_prompt,audio_prompt) VALUES (?,1,0,?,?) ON CONFLICT(source_id) DO UPDATE SET vision_enabled=1,audio_enabled=0,vision_prompt=excluded.vision_prompt',
                (source_id, camera_prompt, 'Audio analysis is disabled.'),
            )
    # Give the gateway time to observe the request, capture media, and finish analysis.
    db.execute('UPDATE schedules SET next_run=?,source_retry_count=0 WHERE task_id=?', ((datetime.now(timezone.utc) + timedelta(seconds=180)).isoformat(), task_id))


def release_task_source_automation(db, task_id: str) -> None:
    source_ids = [row['source_id'] for row in db.execute(
        'SELECT source_id FROM task_source_automation_leases WHERE task_id=?', (task_id,)
    ).fetchall()]
    db.execute('DELETE FROM task_source_automation_leases WHERE task_id=?', (task_id,))
    for source_id in source_ids:
        if db.execute('SELECT 1 FROM task_source_automation_leases WHERE source_id=? LIMIT 1', (source_id,)).fetchone():
            continue
        previous = db.execute('SELECT * FROM source_automation_lease_state WHERE source_id=?', (source_id,)).fetchone()
        if not previous:
            continue
        db.execute('UPDATE sources SET automation_enabled=?,automation_interval_seconds=? WHERE id=?',
                   (previous['previous_enabled'], previous['previous_interval_seconds'], source_id))
        if previous['previous_vision_enabled'] is not None:
            db.execute('UPDATE source_media_settings SET vision_enabled=?,audio_enabled=?,vision_prompt=? WHERE source_id=?',
                       (previous['previous_vision_enabled'], previous['previous_audio_enabled'], previous['previous_vision_prompt'], source_id))
        else:
            db.execute('UPDATE source_media_settings SET vision_enabled=0,audio_enabled=0 WHERE source_id=?', (source_id,))
        db.execute('DELETE FROM source_automation_lease_state WHERE source_id=?', (source_id,))


def event(db, tenant: str, task_id: str, kind: str, data: dict):
    event_id, ts = uid("evt"), now()
    if getattr(db, 'is_postgres', False):
        db.execute('SELECT pg_advisory_xact_lock(76413103)')
    db.execute("INSERT INTO events (id,tenant,task_id,type,occurred_at,data) VALUES (?,?,?,?,?,?)", (event_id, tenant, task_id, kind, ts, json.dumps(data, ensure_ascii=False)))
    for sub in db.execute("SELECT id,event_types FROM subscriptions WHERE tenant=? AND active=1", (tenant,)).fetchall():
        event_types = json.loads(sub["event_types"])
        if "*" not in event_types and kind not in event_types:
            continue
        db.execute("INSERT INTO deliveries (id,subscription_id,event_id,status,next_attempt) VALUES (?,?,?,?,?)", (uid("delivery"), sub[0], event_id, "pending", ts))


def task_dict(row):
    result = dict(row)
    result.pop("tenant", None)
    result.pop("idempotency_key", None)
    result["plan"] = json.loads(result["plan"])
    result["result"] = json.loads(result["result"]) if result["result"] else None
    return result


def event_dict(row):
    result = dict(row)
    result["data"] = json.loads(result["data"])
    return result
