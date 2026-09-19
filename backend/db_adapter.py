"""
db_adapter.py — Smart database adapter that supports both SQLite (local) and PostgreSQL (Railway cloud).

Usage:
  - Set DATABASE_URL env var for PostgreSQL (e.g. Railway)
  - Leave unset to use SQLite (local development)

The adapter translates SQLite-style '?' placeholders to PostgreSQL '%s' automatically,
so all existing service.py queries work without modification.
"""
import os
import re
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("workwise.db_adapter")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL and "postgresql" in DATABASE_URL.lower() or
                    DATABASE_URL and "postgres" in DATABASE_URL.lower())


def _convert_placeholders(query: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL %s placeholders."""
    return query.replace("?", "%s")


def _convert_sqlite_functions(query: str) -> str:
    """Convert SQLite-specific functions/syntax to PostgreSQL equivalents."""
    # datetime('now') → NOW()
    query = re.sub(r"datetime\('now'\)", "NOW()", query, flags=re.IGNORECASE)
    # AUTOINCREMENT → SERIAL (handled in schema, not queries)
    return query


class PostgresRow(dict):
    """Dict-like row that also supports attribute and index access (mimics sqlite3.Row)."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PostgresCursor:
    """Wraps a psycopg2 cursor to mimic sqlite3's cursor interface."""
    def __init__(self, pg_cursor, columns: Optional[list] = None):
        self._cur = pg_cursor
        self._columns = columns

    def execute(self, query: str, params=None):
        query = _convert_placeholders(query)
        query = _convert_sqlite_functions(query)
        if params is not None:
            self._cur.execute(query, params)
        else:
            self._cur.execute(query)
        # Update column names from description
        if self._cur.description:
            self._columns = [desc[0] for desc in self._cur.description]
        else:
            self._columns = []

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = self._columns or []
        return PostgresRow(zip(cols, row))

    def fetchall(self):
        rows = self._cur.fetchall()
        cols = self._columns or []
        return [PostgresRow(zip(cols, row)) for row in rows]

    @property
    def lastrowid(self):
        # After INSERT ... RETURNING id, fetch the returned id
        try:
            row = self._cur.fetchone()
            if row:
                return row[0]
        except Exception:
            pass
        return None

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description


class PostgresConnection:
    """Wraps a psycopg2 connection to mimic sqlite3's connection interface."""
    def __init__(self, pg_conn):
        self._conn = pg_conn
        self._cursor_obj = None

    def cursor(self):
        pg_cur = self._conn.cursor()
        self._cursor_obj = PostgresCursor(pg_cur)
        return self._cursor_obj

    def execute(self, query: str, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    skills TEXT NOT NULL,
    location TEXT NOT NULL,
    working_hours_per_week REAL NOT NULL DEFAULT 40.0,
    working_window_start TEXT NOT NULL DEFAULT '09:00',
    working_window_end TEXT NOT NULL DEFAULT '17:00',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    is_active INTEGER NOT NULL DEFAULT 1,
    is_available INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    required_skills TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    estimated_hours REAL NOT NULL,
    priority TEXT NOT NULL DEFAULT 'Medium',
    urgency TEXT NOT NULL DEFAULT 'Medium',
    deadline TEXT NOT NULL,
    sla_hours REAL NOT NULL DEFAULT 24.0,
    status TEXT NOT NULL DEFAULT 'pending',
    assigned_employee_id INTEGER REFERENCES employees(id),
    assigned_at TEXT,
    completed_at TEXT,
    completed_by_employee_id INTEGER REFERENCES employees(id),
    completed_by_actor TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assignments (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    assigned_at TEXT NOT NULL,
    assigned_by TEXT NOT NULL DEFAULT 'system',
    status TEXT NOT NULL DEFAULT 'active',
    hours_allocated REAL NOT NULL,
    hours_remaining REAL NOT NULL,
    completed_at TEXT,
    unassigned_at TEXT,
    unassigned_reason TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_cycles (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    model_version TEXT NOT NULL DEFAULT 'v1.0.0',
    trigger_reason TEXT NOT NULL DEFAULT 'manual_request'
);

CREATE TABLE IF NOT EXISTS ranked_candidates (
    id SERIAL PRIMARY KEY,
    cycle_id INTEGER NOT NULL REFERENCES recommendation_cycles(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    hard_constraints_passed INTEGER NOT NULL,
    constraint_details TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    rejection_reason TEXT
);

CREATE TABLE IF NOT EXISTS history (
    id SERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    task_id INTEGER,
    task_title TEXT,
    employee_id INTEGER,
    employee_name TEXT,
    previous_employee_id INTEGER,
    previous_employee_name TEXT,
    priority TEXT,
    urgency TEXT,
    deadline TEXT,
    sla TEXT,
    location TEXT,
    estimated_hours REAL,
    remaining_hours_before REAL,
    remaining_hours_after REAL,
    matching_score_or_rank TEXT,
    constraint_checks TEXT,
    trigger_reason TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    timestamp TEXT NOT NULL,
    model_version TEXT,
    notes TEXT,
    before_snapshot TEXT,
    after_snapshot TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_records (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    rows_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    error_log TEXT
);

CREATE TABLE IF NOT EXISTS assistant_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
"""


def _ensure_postgres_tables(pg_conn):
    """Create all tables in PostgreSQL if they don't exist."""
    cur = pg_conn.cursor()
    # Split and run each CREATE TABLE statement
    for stmt in POSTGRES_SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)

    # Insert default settings
    default_settings = [
        ("excel_log_path", "/tmp/allocation_history.xlsx"),
        ("last_excel_sync", ""),
        ("excel_sync_status", "Not available in cloud"),
        ("allocation_policy", "balanced"),
        ("timezone", "UTC"),
        ("model_version", "v1.0.0")
    ]
    for key, val in default_settings:
        cur.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (%s, %s, NOW()) ON CONFLICT (key) DO NOTHING",
            (key, val)
        )
    pg_conn.commit()


def get_postgres_connection():
    """Return a wrapped PostgreSQL connection."""
    try:
        import psycopg2
        # Railway often provides DATABASE_URL with 'postgres://', psycopg2 needs 'postgresql://'
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        pg_conn = psycopg2.connect(url)
        pg_conn.autocommit = False
        return PostgresConnection(pg_conn)
    except ImportError:
        raise RuntimeError("psycopg2 not installed. Add 'psycopg2-binary' to requirements.txt")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        raise


def patch_service_queries_for_postgres(pg_conn: PostgresConnection):
    """
    Monkey-patch the cursor to auto-append RETURNING id after INSERT statements
    so that lastrowid works correctly in PostgreSQL.
    """
    original_execute = pg_conn._conn.cursor().__class__.execute

    class PatchedCursor(PostgresCursor):
        def execute(self, query: str, params=None):
            q = query.strip().rstrip(";")
            # Auto-append RETURNING id for INSERT statements if not already there
            if q.upper().startswith("INSERT") and "RETURNING" not in q.upper():
                q = q + " RETURNING id"
            super().execute(q, params)

    # Replace cursor factory
    original_cursor = pg_conn._conn.cursor

    def patched_cursor():
        pg_cur = original_cursor()
        return PatchedCursor(pg_cur)

    pg_conn._conn.cursor = patched_cursor
    return pg_conn
