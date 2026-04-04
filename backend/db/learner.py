"""學習者上下文 CRUD。"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend.log import get_logger

from .connection import get_conn, get_lock, init_schema, json_parse, new_uuid, now_iso

logger = get_logger(__name__)
from .supabase_client import supabase_enabled, supabase_insert, supabase_select


def learner_context_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_schema()
    now = now_iso()
    tenant_id = str(payload.get("tenant_id", ""))
    profile_id = str(payload.get("profile_id", ""))
    age_band = str(payload.get("age_band", ""))
    region_code = str(payload.get("region_code", ""))
    preferred_language = str(payload.get("preferred_language", "zh-TW"))
    metadata_obj = payload.get("metadata", {})
    metadata = json.dumps(metadata_obj)
    if supabase_enabled():
        try:
            rows = supabase_insert(
                "learner_contexts",
                {
                    "tenant_id": tenant_id,
                    "profile_id": profile_id,
                    "age_band": age_band,
                    "region_code": region_code,
                    "preferred_language": preferred_language,
                    "metadata": metadata_obj or {},
                },
                upsert=True,
                on_conflict="tenant_id,profile_id",
            )
            if isinstance(rows, list) and rows:
                return dict(rows[0])
        except Exception as e:
            logger.warning("learner_context_upsert fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
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
                    (new_uuid(), tenant_id, profile_id, age_band, region_code,
                     preferred_language, metadata, now, now),
                )
            c.commit()
            row = c.execute(
                "SELECT * FROM learner_contexts WHERE tenant_id=? AND profile_id=?",
                (tenant_id, profile_id),
            ).fetchone()
            d = dict(row)
            json_parse(d, "metadata")
            return d
        finally:
            c.close()


def learner_context_get(tenant_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
    init_schema()
    if supabase_enabled():
        try:
            rows = supabase_select(
                "learner_contexts",
                select="age_band,region_code,preferred_language,metadata",
                filters={
                    "tenant_id": f"eq.{tenant_id}",
                    "profile_id": f"eq.{profile_id}",
                },
                limit=1,
            )
            return dict(rows[0]) if rows else None
        except Exception as e:
            logger.warning("learner_context_get fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
        try:
            row = c.execute(
                "SELECT age_band, region_code FROM learner_contexts"
                " WHERE tenant_id=? AND profile_id=? LIMIT 1",
                (tenant_id, profile_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            c.close()
