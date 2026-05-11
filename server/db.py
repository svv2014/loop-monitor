import sqlite3
from datetime import datetime, timezone

DB_PATH = "bounty.db"

MIGRATIONS = [
    (
        "0001_initial",
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            event_type TEXT NOT NULL,
            issue_number INTEGER,
            pr_number INTEGER,
            detail TEXT,
            payload TEXT,
            core_version TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS verdicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            points INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            total_points INTEGER NOT NULL DEFAULT 0,
            verdict_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS issue_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            issue_number INTEGER NOT NULL,
            pr_number INTEGER,
            role TEXT NOT NULL,
            event_type TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            duration_seconds INTEGER,
            rework_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            issue_number INTEGER NOT NULL,
            pr_number INTEGER,
            title TEXT,
            outcome TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            total_duration_seconds INTEGER,
            rework_count INTEGER DEFAULT 0,
            total_bounty INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_events_project_role ON events (project, role);
        CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
        CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at);
        CREATE INDEX IF NOT EXISTS idx_events_issue_number ON events (project, issue_number)
            WHERE issue_number IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_events_pr_number ON events (project, pr_number)
            WHERE pr_number IS NOT NULL;
        """,
    ),
    (
        "0002_add_loop_id",
        "ALTER TABLE events ADD COLUMN loop_id TEXT",
    ),
    (
        "0003_add_pipeline_run_cols",
        "ALTER TABLE pipeline_runs ADD COLUMN issue_lifetime_seconds INTEGER; "
        "ALTER TABLE pipeline_runs ADD COLUMN pr_lifetime_seconds INTEGER",
    ),
]


def _migration_already_applied(conn: sqlite3.Connection, version_id: str) -> bool:
    """Return True if the schema change for version_id is already present in the DB."""
    if version_id == "0001_initial":
        return bool(conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone())
    if version_id == "0002_add_loop_id":
        cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
        return "loop_id" in cols
    if version_id == "0003_add_pipeline_run_cols":
        cols = {r[1] for r in conn.execute("PRAGMA table_info(pipeline_runs)")}
        return "issue_lifetime_seconds" in cols
    return False


def apply_pending_migrations():
    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None  # manual transaction control — required so DDL stays in our transaction
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version_id TEXT PRIMARY KEY,
            applied_at TEXT
        )
    """)

    now = datetime.now(timezone.utc).isoformat()
    applied = {r[0] for r in conn.execute("SELECT version_id FROM schema_migrations")}

    for version_id, sql in MIGRATIONS:
        if version_id in applied:
            continue
        if _migration_already_applied(conn, version_id):
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO schema_migrations (version_id, applied_at) VALUES (?, ?)",
                (version_id, now),
            )
            conn.execute("COMMIT")
            continue
        # Statement splitting: existing MIGRATIONS contain no ';' inside string literals.
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        try:
            conn.execute("BEGIN IMMEDIATE")
            for stmt in statements:
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migrations (version_id, applied_at) VALUES (?, ?)",
                (version_id, now),
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            print(f"Migration failed: {version_id}\nSQL:\n{sql}")
            raise

    conn.close()


def get_db():
    """Direct caller — must close explicitly. Used by background tasks / scripts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def db_dep():
    """FastAPI dependency — opens, yields, closes in finally."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()
