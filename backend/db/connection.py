"""SQLite 連線管理、Schema、遷移。"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from backend.log import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "local.db"
_LEGACY_DB_PATH = Path(__file__).resolve().parent.parent / "local_knowledge.db"

_lock = threading.Lock()
_schema_initialized = False

KNOWLEDGE_COLS = [
    "word", "category", "roots", "breakdown", "definition",
    "meaning", "native_vibe", "example", "synonym_nuance",
    "usage_warning", "memory_hook", "phonetic",
]

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    word       TEXT NOT NULL UNIQUE,
    category   TEXT DEFAULT '',
    roots      TEXT DEFAULT '',
    breakdown  TEXT DEFAULT '',
    definition TEXT DEFAULT '',
    meaning    TEXT DEFAULT '',
    native_vibe TEXT DEFAULT '',
    example    TEXT DEFAULT '',
    synonym_nuance TEXT DEFAULT '',
    usage_warning  TEXT DEFAULT '',
    memory_hook    TEXT DEFAULT '',
    phonetic       TEXT DEFAULT '',
    model          TEXT DEFAULT '',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT DEFAULT '',
    content    TEXT DEFAULT '',
    tags       TEXT DEFAULT '',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS member_storage (
    id                TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    profile_id        TEXT NOT NULL,
    feature           TEXT NOT NULL DEFAULT '',
    title             TEXT NOT NULL DEFAULT '',
    contribution_mode TEXT NOT NULL DEFAULT 'private_use',
    input_text        TEXT NOT NULL DEFAULT '',
    output_text       TEXT NOT NULL DEFAULT '',
    output_json       TEXT NOT NULL DEFAULT '{}',
    metadata          TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_member_storage_profile
    ON member_storage(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_storage_feature
    ON member_storage(profile_id, feature, created_at DESC);

CREATE TABLE IF NOT EXISTS learner_contexts (
    id                 TEXT PRIMARY KEY,
    tenant_id          TEXT NOT NULL,
    profile_id         TEXT NOT NULL,
    age_band           TEXT NOT NULL DEFAULT '',
    region_code        TEXT NOT NULL DEFAULT '',
    preferred_language TEXT NOT NULL DEFAULT 'zh-TW',
    metadata           TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(tenant_id, profile_id)
);

CREATE TABLE IF NOT EXISTS aha_hooks (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    created_by      TEXT,
    topic_key       TEXT NOT NULL,
    hook_type       TEXT NOT NULL,
    hook_variant_id TEXT NOT NULL DEFAULT 'v1',
    hook_title      TEXT NOT NULL DEFAULT '',
    hook_text       TEXT NOT NULL DEFAULT '',
    difficulty_band TEXT NOT NULL DEFAULT 'basic',
    region_tags     TEXT NOT NULL DEFAULT '[]',
    age_tags        TEXT NOT NULL DEFAULT '[]',
    is_active       INTEGER NOT NULL DEFAULT 1,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(tenant_id, topic_key, hook_type, hook_variant_id)
);

CREATE TABLE IF NOT EXISTS aha_events (
    id                 TEXT PRIMARY KEY,
    tenant_id          TEXT NOT NULL,
    profile_id         TEXT NOT NULL,
    attempt_id         TEXT,
    event_type         TEXT NOT NULL,
    hook_id            TEXT,
    hook_variant_id    TEXT,
    topic_key          TEXT NOT NULL,
    question_id        TEXT,
    self_report_delta  INTEGER,
    latency_ms         INTEGER,
    is_correct         INTEGER,
    metadata           TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS learning_attempts (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    profile_id      TEXT NOT NULL,
    topic_key       TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'other',
    started_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ended_at        TEXT,
    pre_confidence  INTEGER,
    post_confidence INTEGER,
    aha_score       REAL,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS click_events (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    page         TEXT NOT NULL DEFAULT '',
    action       TEXT NOT NULL DEFAULT '',
    action_label TEXT NOT NULL DEFAULT '',
    seq          INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_click_events_session
    ON click_events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_click_events_action
    ON click_events(action, created_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def new_uuid() -> str:
    return str(uuid.uuid4())


def get_conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def json_parse(d: Dict[str, Any], *fields: str) -> Dict[str, Any]:
    for f in fields:
        if isinstance(d.get(f), str):
            try:
                d[f] = json.loads(d[f])
            except (json.JSONDecodeError, TypeError):
                d[f] = {}
    return d


def get_lock() -> threading.Lock:
    return _lock


def _migrate_from_legacy(c: sqlite3.Connection) -> None:
    if not _LEGACY_DB_PATH.is_file():
        return
    try:
        row = c.execute("SELECT COUNT(*) FROM knowledge").fetchone()
        if row and row[0] > 0:
            return
        legacy = sqlite3.connect(str(_LEGACY_DB_PATH), check_same_thread=False)
        legacy.row_factory = sqlite3.Row
        try:
            cur = legacy.execute(
                f"SELECT {', '.join(KNOWLEDGE_COLS)} FROM knowledge_cards"
            )
            rows = cur.fetchall()
        finally:
            legacy.close()

        if not rows:
            return

        placeholders = ", ".join("?" for _ in KNOWLEDGE_COLS)
        col_names = ", ".join(f'"{col}"' for col in KNOWLEDGE_COLS)
        updates = ", ".join(
            f'"{k}"=excluded."{k}"' for k in KNOWLEDGE_COLS if k != "word"
        )
        sql = (
            f"INSERT INTO knowledge ({col_names}) VALUES ({placeholders})"
            f" ON CONFLICT(word) DO UPDATE SET {updates}"
        )
        for row in rows:
            vals = [str(row[k] or "") for k in KNOWLEDGE_COLS]
            c.execute(sql, vals)
        c.commit()
        logger.info("已從 local_knowledge.db 遷移 %s 筆資料", len(rows))
    except Exception as e:
        logger.warning("舊資料遷移失敗（可忽略）: %s", e)


def init_schema() -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    with _lock:
        if _schema_initialized:
            return
        c = get_conn()
        try:
            c.executescript(_SCHEMA_SQL)
            c.commit()
            _migrate_from_legacy(c)
            _schema_initialized = True
        finally:
            c.close()
