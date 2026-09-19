import os
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "workwise.db"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL and ("postgresql" in DATABASE_URL or "postgres" in DATABASE_URL))


def get_db():
    """Returns a database connection — PostgreSQL if DATABASE_URL is set, else SQLite."""
    if USE_POSTGRES:
        from backend.db_adapter import get_postgres_connection, _ensure_postgres_tables, PostgresConnection
        conn = get_postgres_connection()
        # Ensure tables exist (idempotent)
        try:
            _ensure_postgres_tables(conn._conn)
        except Exception:
            pass
        # Patch cursor to auto-append RETURNING id for INSERT statements
        _patch_insert_returning(conn)
        return conn
    return _get_sqlite_db()


def _patch_insert_returning(conn):
    """Patch PostgreSQL cursor to auto-add RETURNING id on INSERT for lastrowid support."""
    from backend.db_adapter import PostgresCursor
    import re

    original_cursor_factory = conn._conn.cursor

    class PatchedCursor(PostgresCursor):
        def execute(self, query: str, params=None):
            q = query.strip().rstrip(";")
            if re.match(r"^\s*INSERT\s+", q, re.IGNORECASE) and "RETURNING" not in q.upper():
                q = q + " RETURNING id"
            super().execute(q, params)

        @property
        def lastrowid(self):
            try:
                row = self._cur.fetchone()
                if row:
                    return row[0]
            except Exception:
                pass
            return None

    def patched_cursor_factory():
        pg_cur = original_cursor_factory()
        return PatchedCursor(pg_cur)

    conn._conn.cursor = patched_cursor_factory


def _get_sqlite_db():

    if hasattr(DB_PATH, "parent"):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _ensure_tables(conn)
    return conn

def _ensure_tables(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees';")
    if cursor.fetchone():
        return  # Tables already initialized

    # 1. Employees table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    """)

    # 2. Tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    """)

    # 3. Assignments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    """)

    # 4. Recommendation cycles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendation_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL REFERENCES tasks(id),
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        model_version TEXT NOT NULL DEFAULT 'v1.0.0',
        trigger_reason TEXT NOT NULL DEFAULT 'manual_request'
    );
    """)

    # 5. Ranked candidates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ranked_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id INTEGER NOT NULL REFERENCES recommendation_cycles(id) ON DELETE CASCADE,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        rank INTEGER NOT NULL,
        score REAL NOT NULL,
        hard_constraints_passed INTEGER NOT NULL,
        constraint_details TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        rejection_reason TEXT
    );
    """)

    # 6. History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    """)

    # 7. Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 8. Import records table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        rows_count INTEGER NOT NULL,
        status TEXT NOT NULL,
        error_log TEXT
    );
    """)

    # 9. Assistant sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assistant_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    """)

    default_settings = [
        ("excel_log_path", str(DB_DIR / "history" / "allocation_history.xlsx")),
        ("last_excel_sync", ""),
        ("excel_sync_status", "Never synced"),
        ("allocation_policy", "balanced"),
        ("timezone", "UTC"),
        ("model_version", "v1.0.0")
    ]
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))", (key, val))

    conn.commit()

def init_db():
    conn = get_db()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
