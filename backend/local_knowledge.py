"""
本機 SQLite 知識庫：Supabase 不可用或離線時，仍可查詢與寫入解碼結果。
檔案位置：backend/local_knowledge.db（與舊 knowledge.db 分開，避免結構衝突）
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = Path(__file__).resolve().parent / "local_knowledge.db"

CORE_COLS = [
    "word",
    "category",
    "roots",
    "breakdown",
    "definition",
    "meaning",
    "native_vibe",
    "example",
    "synonym_nuance",
    "usage_warning",
    "memory_hook",
    "phonetic",
]

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_schema() -> None:
    rest = [c for c in CORE_COLS if c != "word"]
    rest_sql = ", ".join(f'"{c}" TEXT' for c in rest)
    with _lock:
        c = _conn()
        try:
            c.execute(
                f"""
                CREATE TABLE IF NOT EXISTS knowledge_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT NOT NULL UNIQUE,
                    {rest_sql},
                    updated_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            c.commit()
        finally:
            c.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = {k: (row[k] or "") if row[k] is not None else "" for k in CORE_COLS}
    if "id" in row.keys():
        d["id"] = row["id"]
    return d


def list_all() -> List[Dict[str, Any]]:
    init_schema()
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                f'SELECT {", ".join(CORE_COLS)} FROM knowledge_cards ORDER BY id DESC'
            )
            return [_row_to_dict(row) for row in cur.fetchall()]
        finally:
            c.close()


def upsert_card(record: Dict[str, Any]) -> None:
    init_schema()
    row = {k: str(record.get(k, "") or "") for k in CORE_COLS}
    if not row["word"].strip():
        return
    placeholders = ", ".join("?" for _ in CORE_COLS)
    updates = ", ".join(f'"{k}"=excluded."{k}"' for k in CORE_COLS if k != "word")
    sql = f"""
    INSERT INTO knowledge_cards ({", ".join(f'"{c}"' for c in CORE_COLS)})
    VALUES ({placeholders})
    ON CONFLICT(word) DO UPDATE SET {updates}, updated_at=datetime('now')
    """
    vals = [row[k] for k in CORE_COLS]
    with _lock:
        c = _conn()
        try:
            c.execute(sql, vals)
            c.commit()
        finally:
            c.close()
