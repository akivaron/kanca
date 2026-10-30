"""One-time, offline SQLite → PostgreSQL import. Never overwrites existing rows."""
import os
import sqlite3
import sys
from pathlib import Path
from app.storage import connect, initialize

TABLES = ('connections','tasks','events','schedules','steps','task_runs','subscriptions','deliveries','conversations','messages','sources','source_events','notification_reads','source_media_settings')
SEQUENCED = {'events','messages','conversations','source_events','deliveries'}


def migrate(path):
    if not os.getenv('DATABASE_URL', '').startswith(('postgresql://','postgres://')):
        raise ValueError('DATABASE_URL PostgreSQL harus dikonfigurasi')
    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise ValueError('File SQLite tidak ditemukan')
    source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    try:
        source.execute('BEGIN')
        initialize()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for table in TABLES:
                if db.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone():
                    raise ValueError('Database PostgreSQL harus kosong; migrasi tidak menimpa data')
            existing = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {}
            for table in TABLES:
                if table not in existing:
                    continue
                target_cols = {row[0] for row in db.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?', (table,))}
                select = f'SELECT rowid AS _legacy_seq,* FROM {table} ORDER BY rowid' if table in SEQUENCED else f'SELECT * FROM {table}'
                rows = source.execute(select)
                counts[table] = 0
                for row in rows:
                    values = dict(row)
                    if table in SEQUENCED:
                        values['seq'] = values.pop('_legacy_seq')
                    values = {key:value for key,value in values.items() if key in target_cols}
                    columns = list(values)
                    placeholders = ','.join('?' for _ in columns)
                    db.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", tuple(values[col] for col in columns))
                    counts[table] += 1
                if table in SEQUENCED:
                    db.execute(f"SELECT setval(pg_get_serial_sequence(?, 'seq'), COALESCE(MAX(seq),1), COUNT(*)>0) FROM {table}", (table,))
            return counts
    finally:
        source.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Gunakan: python -m app.migrate_sqlite /path/database.sqlite')
    try:
        counts = migrate(sys.argv[1])
    except (ValueError, sqlite3.Error) as exc:
        raise SystemExit(str(exc)) from exc
    print('Migrasi selesai:', ', '.join(f'{table}={count}' for table,count in counts.items()))
