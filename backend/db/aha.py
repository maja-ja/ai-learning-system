"""Aha hook 與 aha event CRUD。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from backend.log import get_logger

from .connection import get_conn, get_lock, init_schema, json_parse, new_uuid, now_iso

logger = get_logger(__name__)
from .learner import learner_context_get
from .supabase_client import (
    supabase_enabled,
    supabase_insert,
    supabase_rpc,
    supabase_select,
    supabase_update,
)


def _parse_hook_row(d: Dict[str, Any]) -> Dict[str, Any]:
    for f in ("region_tags", "age_tags"):
        if isinstance(d.get(f), str):
            try:
                d[f] = json.loads(d[f])
            except Exception:
                d[f] = []
    json_parse(d, "metadata")
    d["is_active"] = bool(d.get("is_active", 1))
    return d


def aha_hooks_get_active(tenant_id: str, topic_key: str) -> List[Dict[str, Any]]:
    init_schema()
    if supabase_enabled():
        try:
            rows = supabase_select(
                "aha_hooks",
                filters={
                    "tenant_id": f"eq.{tenant_id}",
                    "topic_key": f"eq.{topic_key}",
                    "is_active": "eq.true",
                },
            )
            return [_parse_hook_row(dict(row)) for row in rows]
        except Exception as e:
            logger.warning("aha_hooks_get_active fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
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
    if supabase_enabled():
        try:
            rows = supabase_select(
                "aha_hooks",
                select="id,hook_variant_id",
                filters={"id": f"in.({','.join(hook_ids)})"},
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("aha_hooks_get_by_ids fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
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
    init_schema()
    now = now_iso()
    hook_id = str(payload.get("id") or new_uuid())
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
    if supabase_enabled():
        try:
            rows = supabase_insert(
                "aha_hooks",
                {
                    "id": hook_id, "tenant_id": tenant_id, "created_by": created_by,
                    "topic_key": topic_key, "hook_type": hook_type,
                    "hook_variant_id": hook_variant_id, "hook_title": hook_title,
                    "hook_text": hook_text, "difficulty_band": difficulty_band,
                    "region_tags": payload.get("region_tags", []),
                    "age_tags": payload.get("age_tags", []),
                    "is_active": bool(is_active),
                    "metadata": payload.get("metadata", {}),
                },
                upsert=True,
                on_conflict="tenant_id,topic_key,hook_type,hook_variant_id",
            )
            if isinstance(rows, list) and rows:
                return _parse_hook_row(dict(rows[0]))
        except Exception as e:
            logger.warning("aha_hook_upsert fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
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
                    hook_id, tenant_id, created_by, topic_key, hook_type, hook_variant_id,
                    hook_title, hook_text, difficulty_band, region_tags, age_tags,
                    is_active, metadata, now, now,
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


def aha_hook_effectiveness_get(
    tenant_id: str, topic_key: str, age_band: str, region_code: str,
) -> List[Dict[str, Any]]:
    init_schema()
    if supabase_enabled():
        try:
            rows = supabase_rpc(
                "aha_hook_effectiveness",
                {"p_tenant_id": tenant_id, "p_topic_key": topic_key,
                 "p_age_band": age_band, "p_region_code": region_code},
            )
            return rows if isinstance(rows, list) else []
        except Exception as e:
            logger.warning("aha_hook_effectiveness_get fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
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


# --- Events ---

def _enrich_event_segments(payload: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(payload)
    if enriched.get("age_band") and enriched.get("region_code"):
        return enriched
    tenant_id = str(enriched.get("tenant_id", "") or "")
    profile_id = str(enriched.get("profile_id", "") or "")
    if not tenant_id or not profile_id:
        return enriched
    context = learner_context_get(tenant_id, profile_id) or {}
    if not enriched.get("age_band"):
        enriched["age_band"] = context.get("age_band")
    if not enriched.get("region_code"):
        enriched["region_code"] = context.get("region_code")
    return enriched


def _pack_event(payload: Dict[str, Any], now: str) -> Tuple:
    is_correct = payload.get("is_correct")
    is_correct_int = None if is_correct is None else (1 if is_correct else 0)
    return (
        payload.get("id") or new_uuid(),
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
    now = now_iso()
    payload = _enrich_event_segments(payload)
    if supabase_enabled():
        try:
            rows = supabase_insert(
                "aha_events",
                {
                    "id": payload.get("id") or new_uuid(),
                    "tenant_id": str(payload.get("tenant_id", "")),
                    "profile_id": str(payload.get("profile_id", "")),
                    "attempt_id": payload.get("attempt_id"),
                    "event_type": str(payload.get("event_type", "")),
                    "hook_id": payload.get("hook_id"),
                    "hook_variant_id": payload.get("hook_variant_id"),
                    "topic_key": str(payload.get("topic_key", "")),
                    "question_id": payload.get("question_id"),
                    "self_report_delta": payload.get("self_report_delta"),
                    "latency_ms": payload.get("latency_ms"),
                    "is_correct": payload.get("is_correct"),
                    "age_band": payload.get("age_band"),
                    "region_code": payload.get("region_code"),
                    "metadata": payload.get("metadata", {}),
                },
            )
            if isinstance(rows, list) and rows:
                return dict(rows[0])
        except Exception as e:
            logger.warning("aha_event_insert fallback to sqlite: %s", e)
    vals = _pack_event(payload, now)
    with get_lock():
        c = get_conn()
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
            row = c.execute("SELECT * FROM aha_events WHERE id=?", (vals[0],)).fetchone()
            d = dict(row)
            json_parse(d, "metadata")
            return d
        finally:
            c.close()


def aha_events_insert_batch(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if supabase_enabled() and events:
        rows_payload = []
        for event in events:
            enriched = _enrich_event_segments(event)
            rows_payload.append({
                "id": enriched.get("id") or new_uuid(),
                "tenant_id": str(enriched.get("tenant_id", "")),
                "profile_id": str(enriched.get("profile_id", "")),
                "attempt_id": enriched.get("attempt_id"),
                "event_type": str(enriched.get("event_type", "")),
                "hook_id": enriched.get("hook_id"),
                "hook_variant_id": enriched.get("hook_variant_id"),
                "topic_key": str(enriched.get("topic_key", "")),
                "question_id": enriched.get("question_id"),
                "self_report_delta": enriched.get("self_report_delta"),
                "latency_ms": enriched.get("latency_ms"),
                "is_correct": enriched.get("is_correct"),
                "age_band": enriched.get("age_band"),
                "region_code": enriched.get("region_code"),
                "metadata": enriched.get("metadata", {}),
            })
        try:
            rows = supabase_insert("aha_events", rows_payload)
            return rows if isinstance(rows, list) else []
        except Exception as e:
            logger.warning("aha_events_insert_batch fallback to sqlite: %s", e)
    return [aha_event_insert(e) for e in events]


def aha_events_needing_variant(
    limit: int, tenant_id: Optional[str]
) -> List[Dict[str, Any]]:
    init_schema()
    if supabase_enabled():
        filters: Dict[str, Any] = {
            "hook_id": "not.is.null",
            "or": "(hook_variant_id.is.null,hook_variant_id.eq.)",
        }
        if tenant_id:
            filters["tenant_id"] = f"eq.{tenant_id}"
        try:
            return supabase_select(
                "aha_events",
                select="id,tenant_id,hook_id,hook_variant_id,created_at",
                filters=filters,
                order="created_at.desc",
                limit=limit,
            )
        except Exception as e:
            logger.warning("aha_events_needing_variant fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
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
    if supabase_enabled():
        try:
            supabase_update("aha_events", {"id": f"eq.{event_id}"}, {"hook_variant_id": hook_variant_id})
            return
        except Exception as e:
            logger.warning("aha_event_update_variant fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
        try:
            c.execute("UPDATE aha_events SET hook_variant_id=? WHERE id=?", (hook_variant_id, event_id))
            c.commit()
        finally:
            c.close()
