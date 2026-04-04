"""會員個人存儲 CRUD。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from backend.log import get_logger

from .connection import get_conn, get_lock, init_schema, json_parse, new_uuid, now_iso

logger = get_logger(__name__)
from .supabase_client import (
    supabase_delete,
    supabase_enabled,
    supabase_insert,
    supabase_select,
)


def member_storage_create(
    tenant_id: str,
    profile_id: str,
    feature: str,
    title: str,
    contribution_mode: str,
    input_text: str = "",
    output_text: str = "",
    output_json: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    init_schema()
    now = now_iso()
    rec_id = new_uuid()
    if supabase_enabled():
        payload = {
            "id": rec_id,
            "tenant_id": tenant_id,
            "profile_id": profile_id,
            "feature": feature,
            "title": title,
            "visibility": "private",
            "contribution_mode": contribution_mode,
            "input_text": input_text,
            "output_text": output_text,
            "output_json": output_json or {},
            "source_model": str((metadata or {}).get("ai_provider") or ""),
            "metadata": metadata or {},
        }
        try:
            rows = supabase_insert("member_storage", payload)
            if isinstance(rows, list) and rows:
                return dict(rows[0])
        except Exception as e:
            logger.warning("member_storage_create fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
        try:
            c.execute(
                "INSERT INTO member_storage"
                " (id, tenant_id, profile_id, feature, title, contribution_mode,"
                "  input_text, output_text, output_json, metadata, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rec_id, tenant_id, profile_id, feature, title, contribution_mode,
                    input_text, output_text,
                    json.dumps(output_json or {}, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now, now,
                ),
            )
            c.commit()
            row = c.execute(
                "SELECT id, tenant_id, profile_id, feature, title, contribution_mode,"
                " input_text, output_text, output_json, metadata, created_at, updated_at"
                " FROM member_storage WHERE id=?",
                (rec_id,),
            ).fetchone()
            return json_parse(dict(row), "output_json", "metadata") if row else {}
        finally:
            c.close()


def member_storage_list(profile_id: str, feature: Optional[str] = None) -> List[Dict[str, Any]]:
    init_schema()
    if supabase_enabled():
        filters: Dict[str, Any] = {"profile_id": f"eq.{profile_id}"}
        if feature:
            filters["feature"] = f"eq.{feature}"
        try:
            return supabase_select(
                "member_storage", filters=filters, order="created_at.desc", limit=100,
            )
        except Exception as e:
            logger.warning("member_storage_list fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
        try:
            if feature:
                cur = c.execute(
                    "SELECT id, tenant_id, profile_id, feature, title, contribution_mode,"
                    " input_text, output_text, output_json, metadata, created_at, updated_at"
                    " FROM member_storage WHERE profile_id=? AND feature=?"
                    " ORDER BY created_at DESC LIMIT 100",
                    (profile_id, feature),
                )
            else:
                cur = c.execute(
                    "SELECT id, tenant_id, profile_id, feature, title, contribution_mode,"
                    " input_text, output_text, output_json, metadata, created_at, updated_at"
                    " FROM member_storage WHERE profile_id=?"
                    " ORDER BY created_at DESC LIMIT 100",
                    (profile_id,),
                )
            return [json_parse(dict(row), "output_json", "metadata") for row in cur.fetchall()]
        finally:
            c.close()


def member_storage_delete(profile_id: str, record_id: str) -> bool:
    init_schema()
    if supabase_enabled():
        try:
            rows = supabase_delete(
                "member_storage",
                {"id": f"eq.{record_id}", "profile_id": f"eq.{profile_id}"},
            )
            return bool(rows)
        except Exception as e:
            logger.warning("member_storage_delete fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
        try:
            cur = c.execute(
                "DELETE FROM member_storage WHERE id=? AND profile_id=?",
                (record_id, profile_id),
            )
            c.commit()
            return cur.rowcount > 0
        finally:
            c.close()
