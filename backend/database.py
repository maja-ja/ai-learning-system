"""本機 SQLite 資料庫統一層

取代原 Supabase 雲端依賴，所有資料儲存於 backend/local.db。
線程安全（threading.Lock）。

首次啟動時若偵測到舊版 local_knowledge.db，會自動將資料遷移過來。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = Path(__file__).resolve().parent / "local.db"
_LEGACY_DB_PATH = Path(__file__).resolve().parent / "local_knowledge.db"

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _uuid() -> str:
    return str(uuid.uuid4())


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _json_parse(d: Dict[str, Any], *fields: str) -> Dict[str, Any]:
    for f in fields:
        if isinstance(d.get(f), str):
            try:
                d[f] = json.loads(d[f])
            except (json.JSONDecodeError, TypeError):
                d[f] = {}
    return d


def _migrate_from_legacy(c: sqlite3.Connection) -> None:
    """從舊版 local_knowledge.db 的 knowledge_cards 資料表遷移資料（僅首次）。"""
    if not _LEGACY_DB_PATH.is_file():
        return
    try:
        row = c.execute("SELECT COUNT(*) FROM knowledge").fetchone()
        if row and row[0] > 0:
            return  # 已有資料，跳過遷移
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
        print(f"[database] 已從 local_knowledge.db 遷移 {len(rows)} 筆資料")
    except Exception as e:
        print(f"[database] 舊資料遷移失敗（可忽略）: {e}")


def init_schema() -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    with _lock:
        if _schema_initialized:
            return
        c = _conn()
        try:
            c.executescript(_SCHEMA_SQL)
            c.commit()
            _migrate_from_legacy(c)
            _schema_initialized = True
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------

def knowledge_list() -> List[Dict[str, Any]]:
    init_schema()
    with _lock:
        c = _conn()
        try:
            cur = c.execute("SELECT * FROM knowledge ORDER BY created_at DESC")
            return [dict(row) for row in cur.fetchall()]
        finally:
            c.close()


def knowledge_upsert(record: Dict[str, Any]) -> None:
    init_schema()
    row = {k: str(record.get(k, "") or "") for k in KNOWLEDGE_COLS}
    if not row["word"].strip():
        return
    col_names = ", ".join(f'"{c}"' for c in KNOWLEDGE_COLS)
    placeholders = ", ".join("?" for _ in KNOWLEDGE_COLS)
    updates = ", ".join(f'"{k}"=excluded."{k}"' for k in KNOWLEDGE_COLS if k != "word")
    updates += ", updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')"
    sql = (
        f"INSERT INTO knowledge ({col_names}) VALUES ({placeholders})"
        f" ON CONFLICT(word) DO UPDATE SET {updates}"
    )
    vals = [row[k] for k in KNOWLEDGE_COLS]
    with _lock:
        c = _conn()
        try:
            c.execute(sql, vals)
            c.commit()
        finally:
            c.close()


def knowledge_delete_all() -> int:
    """刪除 knowledge 表全部列（舊詞條），回傳刪除筆數（無法取得時為 -1）。"""
    init_schema()
    with _lock:
        c = _conn()
        try:
            cur = c.execute("DELETE FROM knowledge")
            c.commit()
            n = cur.rowcount
            return int(n) if n is not None and n >= 0 else -1
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def notes_list() -> List[Dict[str, Any]]:
    init_schema()
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                "SELECT id, title, content, tags, created_at, updated_at"
                " FROM notes ORDER BY id DESC"
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            c.close()


def notes_create(title: str, content: str, tags: str) -> Dict[str, Any]:
    init_schema()
    now = _now()
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                "INSERT INTO notes (title, content, tags, created_at, updated_at)"
                " VALUES (?,?,?,?,?)",
                (title, content, tags, now, now),
            )
            c.commit()
            row = c.execute(
                "SELECT id, title, content, tags, created_at, updated_at"
                " FROM notes WHERE id=?",
                (cur.lastrowid,),
            ).fetchone()
            return dict(row) if row else {}
        finally:
            c.close()


def notes_update(note_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    init_schema()
    allowed = {"title", "content", "tags"}
    clean = {k: v for k, v in data.items() if k in allowed}
    if not clean:
        return None
    now = _now()
    fields = ", ".join(f'"{k}"=?' for k in clean)
    vals = list(clean.values()) + [now, note_id]
    with _lock:
        c = _conn()
        try:
            c.execute(f"UPDATE notes SET {fields}, updated_at=? WHERE id=?", vals)
            c.commit()
            row = c.execute(
                "SELECT id, title, content, tags, created_at, updated_at"
                " FROM notes WHERE id=?",
                (note_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            c.close()


def notes_delete(note_id: int) -> None:
    init_schema()
    with _lock:
        c = _conn()
        try:
            c.execute("DELETE FROM notes WHERE id=?", (note_id,))
            c.commit()
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Learner contexts
# ---------------------------------------------------------------------------

def learner_context_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_schema()
    now = _now()
    tenant_id = str(payload.get("tenant_id", ""))
    profile_id = str(payload.get("profile_id", ""))
    age_band = str(payload.get("age_band", ""))
    region_code = str(payload.get("region_code", ""))
    preferred_language = str(payload.get("preferred_language", "zh-TW"))
    metadata = json.dumps(payload.get("metadata", {}))
    with _lock:
        c = _conn()
        try:
            existing = c.execute(
                "SELECT id FROM learner_contexts WHERE tenant_id=? AND profile_id=?",
                (tenant_id, profile_id),
            ).fetchone()
            if existing:
                c.execute(
                    "UPDATE learner_contexts"
                    " SET age_band=?, region_code=?, preferred_language=?, metadata=?, updated_at=?"
                    " WHERE tenant_id=? AND profile_id=?",
                    (age_band, region_code, preferred_language, metadata, now,
                     tenant_id, profile_id),
                )
            else:
                c.execute(
                    "INSERT INTO learner_contexts"
                    " (id, tenant_id, profile_id, age_band, region_code,"
                    "  preferred_language, metadata, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (_uuid(), tenant_id, profile_id, age_band, region_code,
                     preferred_language, metadata, now, now),
                )
            c.commit()
            row = c.execute(
                "SELECT * FROM learner_contexts WHERE tenant_id=? AND profile_id=?",
                (tenant_id, profile_id),
            ).fetchone()
            d = dict(row)
            _json_parse(d, "metadata")
            return d
        finally:
            c.close()


def learner_context_get(tenant_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
    init_schema()
    with _lock:
        c = _conn()
        try:
            row = c.execute(
                "SELECT age_band, region_code FROM learner_contexts"
                " WHERE tenant_id=? AND profile_id=? LIMIT 1",
                (tenant_id, profile_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Aha hooks
# ---------------------------------------------------------------------------

def _parse_hook_row(d: Dict[str, Any]) -> Dict[str, Any]:
    for f in ("region_tags", "age_tags"):
        if isinstance(d.get(f), str):
            try:
                d[f] = json.loads(d[f])
            except Exception:
                d[f] = []
    _json_parse(d, "metadata")
    d["is_active"] = bool(d.get("is_active", 1))
    return d


def aha_hooks_get_active(tenant_id: str, topic_key: str) -> List[Dict[str, Any]]:
    init_schema()
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                "SELECT * FROM aha_hooks"
                " WHERE tenant_id=? AND topic_key=? AND is_active=1",
                (tenant_id, topic_key),
            )
            return [_parse_hook_row(dict(row)) for row in cur.fetchall()]
        finally:
            c.close()


def aha_hooks_get_by_ids(hook_ids: List[str]) -> List[Dict[str, Any]]:
    init_schema()
    if not hook_ids:
        return []
    with _lock:
        c = _conn()
        try:
            placeholders = ",".join("?" for _ in hook_ids)
            cur = c.execute(
                f"SELECT id, hook_variant_id FROM aha_hooks WHERE id IN ({placeholders})",
                hook_ids,
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            c.close()


def aha_hook_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
    """依 (tenant_id, topic_key, hook_type, hook_variant_id) 寫入或更新一筆 hook。"""
    init_schema()
    now = _now()
    hook_id = str(payload.get("id") or _uuid())
    tenant_id = str(payload.get("tenant_id", ""))
    created_by = payload.get("created_by")
    topic_key = str(payload.get("topic_key", ""))
    hook_type = str(payload.get("hook_type", ""))
    hook_variant_id = str(payload.get("hook_variant_id", "v1"))
    hook_title = str(payload.get("hook_title", ""))
    hook_text = str(payload.get("hook_text", ""))
    difficulty_band = str(payload.get("difficulty_band", "basic"))
    region_tags = json.dumps(payload.get("region_tags", []))
    age_tags = json.dumps(payload.get("age_tags", []))
    is_active = 1 if payload.get("is_active", True) else 0
    metadata = json.dumps(payload.get("metadata", {}))
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO aha_hooks ("
                " id, tenant_id, created_by, topic_key, hook_type, hook_variant_id,"
                " hook_title, hook_text, difficulty_band, region_tags, age_tags,"
                " is_active, metadata, created_at, updated_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(tenant_id, topic_key, hook_type, hook_variant_id) DO UPDATE SET"
                " hook_title=excluded.hook_title,"
                " hook_text=excluded.hook_text,"
                " difficulty_band=excluded.difficulty_band,"
                " region_tags=excluded.region_tags,"
                " age_tags=excluded.age_tags,"
                " is_active=excluded.is_active,"
                " metadata=excluded.metadata,"
                " updated_at=excluded.updated_at",
                (
                    hook_id,
                    tenant_id,
                    created_by,
                    topic_key,
                    hook_type,
                    hook_variant_id,
                    hook_title,
                    hook_text,
                    difficulty_band,
                    region_tags,
                    age_tags,
                    is_active,
                    metadata,
                    now,
                    now,
                ),
            )
            c.commit()
            row = c.execute(
                "SELECT * FROM aha_hooks WHERE tenant_id=? AND topic_key=?"
                " AND hook_type=? AND hook_variant_id=?",
                (tenant_id, topic_key, hook_type, hook_variant_id),
            ).fetchone()
            d = dict(row) if row else {}
            return _parse_hook_row(d)
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Aha hook effectiveness（aha_hook_effectiveness_view 的 SQLite 近似版）
# ---------------------------------------------------------------------------

def aha_hook_effectiveness_get(
    tenant_id: str,
    topic_key: str,
    age_band: str,
    region_code: str,
) -> List[Dict[str, Any]]:
    init_schema()
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                """
                SELECT
                    COALESCE(h.hook_type, 'unknown') AS hook_type,
                    COALESCE(e.hook_variant_id, h.hook_variant_id, 'unknown') AS hook_variant_id,
                    COUNT(CASE WHEN e.event_type='hint_shown'   THEN 1 END) AS impressions,
                    COUNT(CASE WHEN e.event_type='aha_reported' THEN 1 END) AS aha_reports,
                    AVG(CASE WHEN e.event_type='question_answered'
                              AND COALESCE(e.hook_variant_id,'') != ''
                         THEN CAST(e.is_correct AS REAL) END) AS correct_after_hook,
                    (
                        AVG(CASE WHEN e.event_type='question_answered'
                                  AND COALESCE(e.hook_variant_id,'') != ''
                             THEN CAST(e.is_correct AS REAL) END)
                        -
                        AVG(CASE WHEN e.event_type='question_answered'
                                  AND COALESCE(e.hook_variant_id,'') = ''
                             THEN CAST(e.is_correct AS REAL) END)
                    ) AS lift,
                    AVG(CASE WHEN e.event_type='aha_reported' AND e.latency_ms IS NOT NULL
                         THEN CAST(e.latency_ms AS REAL) END) AS time_to_aha
                FROM aha_events e
                LEFT JOIN aha_hooks h ON h.id = e.hook_id
                WHERE e.tenant_id=? AND e.topic_key=?
                GROUP BY
                    COALESCE(h.hook_type, 'unknown'),
                    COALESCE(e.hook_variant_id, h.hook_variant_id, 'unknown')
                """,
                (tenant_id, topic_key),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Aha events
# ---------------------------------------------------------------------------

def _pack_event(payload: Dict[str, Any], now: str) -> Tuple:
    is_correct = payload.get("is_correct")
    is_correct_int = None if is_correct is None else (1 if is_correct else 0)
    return (
        payload.get("id") or _uuid(),
        str(payload.get("tenant_id", "")),
        str(payload.get("profile_id", "")),
        payload.get("attempt_id"),
        str(payload.get("event_type", "")),
        payload.get("hook_id"),
        payload.get("hook_variant_id"),
        str(payload.get("topic_key", "")),
        payload.get("question_id"),
        payload.get("self_report_delta"),
        payload.get("latency_ms"),
        is_correct_int,
        json.dumps(payload.get("metadata", {})),
        now,
    )


def aha_event_insert(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_schema()
    now = _now()
    vals = _pack_event(payload, now)
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO aha_events"
                " (id, tenant_id, profile_id, attempt_id, event_type, hook_id,"
                "  hook_variant_id, topic_key, question_id, self_report_delta,"
                "  latency_ms, is_correct, metadata, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                vals,
            )
            c.commit()
            row = c.execute(
                "SELECT * FROM aha_events WHERE id=?", (vals[0],)
            ).fetchone()
            d = dict(row)
            _json_parse(d, "metadata")
            return d
        finally:
            c.close()


def aha_events_insert_batch(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [aha_event_insert(e) for e in events]


def aha_events_needing_variant(
    limit: int, tenant_id: Optional[str]
) -> List[Dict[str, Any]]:
    init_schema()
    with _lock:
        c = _conn()
        try:
            if tenant_id:
                cur = c.execute(
                    "SELECT id, tenant_id, hook_id, hook_variant_id, created_at"
                    " FROM aha_events"
                    " WHERE tenant_id=? AND hook_id IS NOT NULL"
                    "   AND (hook_variant_id IS NULL OR hook_variant_id='')"
                    " ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, limit),
                )
            else:
                cur = c.execute(
                    "SELECT id, tenant_id, hook_id, hook_variant_id, created_at"
                    " FROM aha_events"
                    " WHERE hook_id IS NOT NULL"
                    "   AND (hook_variant_id IS NULL OR hook_variant_id='')"
                    " ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]
        finally:
            c.close()


def aha_event_update_variant(event_id: str, hook_variant_id: str) -> None:
    init_schema()
    with _lock:
        c = _conn()
        try:
            c.execute(
                "UPDATE aha_events SET hook_variant_id=? WHERE id=?",
                (hook_variant_id, event_id),
            )
            c.commit()
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Admin / status
# ---------------------------------------------------------------------------

def table_count(table_name: str) -> int:
    init_schema()
    allowed = {"learner_contexts", "aha_hooks", "learning_attempts", "aha_events"}
    if table_name not in allowed:
        return 0
    with _lock:
        c = _conn()
        try:
            row = c.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0
        finally:
            c.close()


def db_status_snapshot() -> Dict[str, Any]:
    return {
        "backend_mode": "local_sqlite",
        "supabase_ok": False,
        "postgres_dsn_configured": False,
        "active_write_adapter": "local-sqlite",
        "db_path": str(DB_PATH),
    }


# ---------------------------------------------------------------------------
# Click tracking & Markov prediction
# ---------------------------------------------------------------------------

def click_events_insert_batch(
    session_id: str, events: List[Dict[str, Any]]
) -> int:
    """批次寫入點擊事件，回傳成功寫入筆數。"""
    init_schema()
    if not events:
        return 0
    now = _now()
    rows = []
    for e in events:
        rows.append((
            _uuid(),
            session_id,
            str(e.get("page", "")),
            str(e.get("action", "")),
            str(e.get("action_label", "")),
            int(e.get("seq", 0)),
            now,
        ))
    with _lock:
        c = _conn()
        try:
            c.executemany(
                "INSERT OR IGNORE INTO click_events"
                " (id, session_id, page, action, action_label, seq, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                rows,
            )
            c.commit()
            return len(rows)
        finally:
            c.close()


def click_recent_actions(session_id: str, limit: int = 5) -> List[str]:
    """取得該 session 最近 N 次 action（由舊到新）。"""
    init_schema()
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                "SELECT action FROM click_events"
                " WHERE session_id=? ORDER BY seq DESC, created_at DESC LIMIT ?",
                (session_id, limit),
            )
            rows = [r[0] for r in cur.fetchall()]
            return list(reversed(rows))
        finally:
            c.close()


def click_markov_predict(
    recent_actions: List[str], limit: int = 5
) -> List[Dict[str, Any]]:
    """
    一階 Markov 預測：給定最後一個 action，從全部歷史找最常見的後繼 action。
    回傳 [{"action": str, "label": str, "count": int, "prob": float}, ...]。
    """
    init_schema()
    if not recent_actions:
        # 沒有任何歷史，回傳全站最熱門 action
        with _lock:
            c = _conn()
            try:
                cur = c.execute(
                    "SELECT action, action_label, COUNT(*) AS cnt"
                    " FROM click_events"
                    " WHERE action != ''"
                    " GROUP BY action ORDER BY cnt DESC LIMIT ?",
                    (limit,),
                )
                rows = cur.fetchall()
                total = sum(r[2] for r in rows) or 1
                return [
                    {"action": r[0], "label": r[1], "count": r[2],
                     "prob": round(r[2] / total, 3)}
                    for r in rows
                ]
            finally:
                c.close()

    last_action = recent_actions[-1]
    with _lock:
        c = _conn()
        try:
            # 找出在 last_action 之後出現過哪些 action（跨所有 session 的一階轉移）
            cur = c.execute(
                """
                SELECT e2.action, e2.action_label, COUNT(*) AS cnt
                FROM click_events e1
                JOIN click_events e2
                  ON  e1.session_id = e2.session_id
                  AND e2.seq = e1.seq + 1
                WHERE e1.action = ?
                  AND e2.action != ''
                GROUP BY e2.action
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (last_action, limit),
            )
            rows = cur.fetchall()
            total = sum(r[2] for r in rows) or 1
            return [
                {"action": r[0], "label": r[1] or r[0], "count": r[2],
                 "prob": round(r[2] / total, 3)}
                for r in rows
            ]
        finally:
            c.close()
