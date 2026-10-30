import sys
from types import SimpleNamespace
from app.storage import PostgresConnection, DatabaseRow


def test_postgres_adapter_translates_parameters_and_legacy_queries(monkeypatch):
    calls = []
    class FakeConnection:
        def execute(self, query, params=()):
            calls.append((query, params))
            return None
        def close(self): pass
    monkeypatch.setitem(sys.modules, 'psycopg', SimpleNamespace(connect=lambda *args, **kwargs: FakeConnection()))
    db = PostgresConnection('postgresql://example')
    db.execute('SELECT rowid AS cursor FROM events WHERE tenant=? AND rowid>?', ('tenant', 7))
    db.execute('INSERT OR IGNORE INTO notification_reads VALUES (?,?,?)', ('tenant','evt','time'))
    db.execute('BEGIN IMMEDIATE')
    assert calls[0] == ('SELECT seq AS cursor FROM events WHERE tenant=%s AND seq>%s', ('tenant',7))
    assert calls[1][0] == 'INSERT INTO notification_reads VALUES (%s,%s,%s) ON CONFLICT DO NOTHING'
    assert 'pg_advisory_xact_lock' in calls[2][0]
    row = DatabaseRow([('a',1),('b',2)])
    assert row[0] == 1 and row['b'] == 2
