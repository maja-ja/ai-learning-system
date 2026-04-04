"""知識庫 CRUD。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .connection import KNOWLEDGE_COLS, get_conn, get_lock, init_schema
from .supabase_client import (
    supabase_enabled,
    supabase_insert,
    supabase_select,
    supabase_update,
)


def knowledge_list() -> List[Dict[str, Any]]:
    init_schema()
    with get_lock():
        c = get_conn()
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
    with get_lock():
        c = get_conn()
        try:
            c.execute(sql, vals)
            c.commit()
        finally:
            c.close()


def knowledge_sync_to_supabase(
    tenant_id: str,
    created_by: Optional[str],
    record: Dict[str, Any],
) -> None:
    if not supabase_enabled():
        return
    row = {k: str(record.get(k, "") or "") for k in KNOWLEDGE_COLS}
    word = row.get("word", "").strip()
    if not tenant_id or not word:
        return
    payload: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "created_by": created_by,
        "word": word,
        "category": row["category"],
        "roots": row["roots"],
        "breakdown": row["breakdown"],
        "definition": row["definition"],
        "meaning": row["meaning"],
        "native_vibe": row["native_vibe"],
        "example": row["example"],
        "synonym_nuance": row["synonym_nuance"],
        "usage_warning": row["usage_warning"],
        "memory_hook": row["memory_hook"],
        "phonetic": row["phonetic"],
        "model": str(record.get("model", "") or "") or None,
        "status": "published",
    }
    rows = supabase_select(
        "etymon_entries",
        select="id",
        filters={"tenant_id": f"eq.{tenant_id}", "word": f"eq.{word}"},
        limit=1,
    )
    if rows:
        supabase_update("etymon_entries", {"id": f"eq.{rows[0]['id']}"}, payload)
    else:
        supabase_insert("etymon_entries", payload)


def knowledge_delete_all() -> int:
    init_schema()
    with get_lock():
        c = get_conn()
        try:
            cur = c.execute("DELETE FROM knowledge")
            c.commit()
            n = cur.rowcount
            return int(n) if n is not None and n >= 0 else -1
        finally:
            c.close()
