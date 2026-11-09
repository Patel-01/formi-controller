"""SQLite store — WAL mode for crash safety."""
import sqlite3
import json

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, val TEXT);

CREATE TABLE IF NOT EXISTS calls (
    event_id  INTEGER PRIMARY KEY,
    ts        TEXT    NOT NULL,
    workflow_id TEXT  NOT NULL,
    cohort_id   TEXT,
    welcome_message TEXT,
    voice       TEXT,
    caller_id   TEXT,
    prompt_version TEXT,
    connected   INTEGER NOT NULL DEFAULT 0,
    engaged     INTEGER NOT NULL DEFAULT 0,
    hallucination_flag INTEGER,
    config_version INTEGER
);
CREATE INDEX IF NOT EXISTS c_wf    ON calls(workflow_id, ts);
CREATE INDEX IF NOT EXISTS c_did   ON calls(workflow_id, caller_id);
CREATE INDEX IF NOT EXISTS c_pv    ON calls(workflow_id, prompt_version, ts);
CREATE INDEX IF NOT EXISTS c_voice ON calls(workflow_id, voice, ts);
CREATE INDEX IF NOT EXISTS c_wm    ON calls(workflow_id, welcome_message, ts);

CREATE TABLE IF NOT EXISTS experiments (
    exp_id      TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    dim         TEXT NOT NULL,
    cohort_id   TEXT,          -- NULL = global experiment; non-NULL = per-cohort (C2)
    status      TEXT NOT NULL DEFAULT 'active',
    started_ts  TEXT NOT NULL,
    concluded_ts TEXT,
    winner      TEXT,
    arms_json   TEXT NOT NULL
);

-- Migration: add cohort_id if upgrading from an older schema
CREATE INDEX IF NOT EXISTS exp_cohort ON experiments(workflow_id, dim, cohort_id, status);

CREATE TABLE IF NOT EXISTS proposals (
    prop_id     TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',
    approval_id TEXT,
    base_version INTEGER,
    config_json TEXT,
    submitted_ts TEXT,
    summary     TEXT
);

CREATE TABLE IF NOT EXISTS audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    action      TEXT NOT NULL,
    detail      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hallucination_incidents (
    incident_id  TEXT PRIMARY KEY,
    workflow_id  TEXT NOT NULL,
    detected_ts  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open',
    prompt_before TEXT,
    prompt_after  TEXT,
    validation_run_id TEXT
);
"""


_MIGRATIONS = [
    # C2: add cohort_id to experiments (safe no-op if already present)
    "ALTER TABLE experiments ADD COLUMN cohort_id TEXT",
]


def open_db(path: str = "controller.db"):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
        except Exception:
            pass  # column already exists
    conn.commit()
    return conn


def kv_get(conn, key, default=None):
    row = conn.execute("SELECT val FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def kv_set(conn, key, val):
    conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(val)))


def add_audit(conn, ts: str, workflow_id: str, action: str, detail):
    d = json.dumps(detail) if not isinstance(detail, str) else detail
    conn.execute("INSERT INTO audit VALUES (NULL,?,?,?,?)", (ts, workflow_id, action, d))
