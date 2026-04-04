"""筆記 CRUD。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .connection import get_conn, get_lock, init_schema, now_iso


def notes_list() -> List[Dict[str, Any]]:
    init_schema()
    with get_lock():
        c = get_conn()
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
    now = now_iso()
    with get_lock():
        c = get_conn()
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
    now = now_iso()
    fields = ", ".join(f'"{k}"=?' for k in clean)
    vals = list(clean.values()) + [now, note_id]
    with get_lock():
        c = get_conn()
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
    with get_lock():
        c = get_conn()
        try:
            c.execute("DELETE FROM notes WHERE id=?", (note_id,))
            c.commit()
        finally:
            c.close()
