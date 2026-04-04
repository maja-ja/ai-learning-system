"""點擊事件追蹤與 Markov 預測。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.log import get_logger

from .connection import get_conn, get_lock, init_schema, new_uuid, now_iso

logger = get_logger(__name__)
from .supabase_client import supabase_enabled, supabase_insert, supabase_rpc, supabase_select


def click_events_insert_batch(
    session_id: str,
    events: List[Dict[str, Any]],
    tenant_id: Optional[str] = None,
    profile_id: Optional[str] = None,
) -> int:
    init_schema()
    if not events:
        return 0
    if supabase_enabled():
        rows_payload = []
        for e in events:
            rows_payload.append({
                "tenant_id": tenant_id,
                "profile_id": profile_id,
                "session_id": session_id,
                "page": str(e.get("page", "")),
                "action": str(e.get("action", "")),
                "action_label": str(e.get("action_label", "")),
                "seq": int(e.get("seq", 0)),
                "metadata": e.get("metadata", {}) or {},
            })
        try:
            rows = supabase_insert(
                "click_events", rows_payload, upsert=True, on_conflict="session_id,seq",
            )
            return len(rows) if isinstance(rows, list) else len(rows_payload)
        except Exception as e:
            logger.warning("click_events_insert_batch fallback to sqlite: %s", e)
    now = now_iso()
    rows = []
    for e in events:
        rows.append((
            new_uuid(), session_id,
            str(e.get("page", "")), str(e.get("action", "")),
            str(e.get("action_label", "")), int(e.get("seq", 0)), now,
        ))
    with get_lock():
        c = get_conn()
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
    init_schema()
    if supabase_enabled():
        try:
            rows = supabase_select(
                "click_events",
                select="action",
                filters={"session_id": f"eq.{session_id}"},
                order="seq.desc,created_at.desc",
                limit=limit,
            )
            actions = [str(r.get("action", "")) for r in rows if r.get("action")]
            return list(reversed(actions))
        except Exception as e:
            logger.warning("click_recent_actions fallback to sqlite: %s", e)
    with get_lock():
        c = get_conn()
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
    recent_actions: List[str], limit: int = 5,
) -> List[Dict[str, Any]]:
    init_schema()
    if supabase_enabled():
        try:
            rows = supabase_rpc(
                "predict_click_actions",
                {"p_last_action": recent_actions[-1] if recent_actions else None, "p_limit": limit},
            )
            return rows if isinstance(rows, list) else []
        except Exception as e:
            logger.warning("click_markov_predict fallback to sqlite: %s", e)
    if not recent_actions:
        with get_lock():
            c = get_conn()
            try:
                cur = c.execute(
                    "SELECT action, action_label, COUNT(*) AS cnt"
                    " FROM click_events WHERE action != ''"
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
    with get_lock():
        c = get_conn()
        try:
            cur = c.execute(
                """
                SELECT e2.action, e2.action_label, COUNT(*) AS cnt
                FROM click_events e1
                JOIN click_events e2
                  ON  e1.session_id = e2.session_id
                  AND e2.seq = e1.seq + 1
                WHERE e1.action = ? AND e2.action != ''
                GROUP BY e2.action ORDER BY cnt DESC LIMIT ?
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
