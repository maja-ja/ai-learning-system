"""學習嘗試紀錄 CRUD。"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend.log import get_logger

from .connection import get_conn, get_lock, init_schema, json_parse, new_uuid, now_iso

logger = get_logger(__name__)
from .supabase_client import supabase_enabled, supabase_insert, supabase_update


def learning_attempt_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_schema()
    now = now_iso()
    rec_id = str(payload.get("id") or new_uuid())
    tenant_id = str(payload.get("tenant_id", ""))
    profile_id = str(payload.get("profile_id", ""))
    row = {
        "id": rec_id,
        "tenant_id": tenant_id,
        "profile_id": profile_id,
        "topic_key": str(payload.get("topic_key", "")),
        "source": str(payload.get("source", "lab")),
        "started_at": payload.get("started_at") or now,
        "pre_confidence": payload.get("pre_confidence"),
        "metadata": payload.get("metadata", {}),
    }
    if supabase_enabled():
        try:
            rows = supabase_insert("learning_attempts", row)
            if isinstance(rows, list) and rows:
                return dict(rows[0])
        except Exception as e:
            logger.warning("learning_attempt_create fallback to sqlite: %s", e)
    metadata = json.dumps(payload.get("metadata", {}))
    with get_lock():
        c = get_conn()
        try:
            c.execute(
                "INSERT INTO learning_attempts"
                " (id, tenant_id, profile_id, topic_key, source, started_at,"
                "  pre_confidence, metadata, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rec_id, tenant_id, profile_id, row["topic_key"], row["source"],
                 row["started_at"], row["pre_confidence"], metadata, now, now),
            )
            c.commit()
            stored = c.execute("SELECT * FROM learning_attempts WHERE id=?", (rec_id,)).fetchone()
            d = dict(stored) if stored else {}
            json_parse(d, "metadata")
            return d
        finally:
            c.close()


def learning_attempt_update(attempt_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    init_schema()
    clean: Dict[str, Any] = {}
    for key in ("ended_at", "post_confidence", "aha_score"):
        if key in payload:
            clean[key] = payload.get(key)
    if "metadata" in payload:
        clean["metadata"] = payload.get("metadata") or {}
    if not clean:
        return None
    if supabase_enabled():
        try:
            rows = supabase_update("learning_attempts", {"id": f"eq.{attempt_id}"}, clean)
            return dict(rows[0]) if rows else None
        except Exception as e:
            logger.warning("learning_attempt_update fallback to sqlite: %s", e)
    now = now_iso()
    with get_lock():
        c = get_conn()
        try:
            fields = []
            values = []
            for key, value in clean.items():
                fields.append(f"{key}=?")
                values.append(json.dumps(value) if key == "metadata" else value)
            fields.append("updated_at=?")
            values.extend([now, attempt_id])
            c.execute(
                f"UPDATE learning_attempts SET {', '.join(fields)} WHERE id=?",
                values,
            )
            c.commit()
            stored = c.execute("SELECT * FROM learning_attempts WHERE id=?", (attempt_id,)).fetchone()
            d = dict(stored) if stored else None
            if d:
                json_parse(d, "metadata")
            return d
        finally:
            c.close()
