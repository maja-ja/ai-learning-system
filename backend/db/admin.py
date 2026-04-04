"""管理與狀態查詢。"""
from __future__ import annotations

from typing import Any, Dict

from .connection import DB_PATH, get_conn, get_lock, init_schema
from .supabase_client import supabase_enabled, supabase_select


def table_count(table_name: str) -> int:
    init_schema()
    allowed = {
        "learner_contexts", "aha_hooks", "learning_attempts",
        "aha_events", "member_storage", "click_events",
    }
    if table_name not in allowed:
        return 0
    if supabase_enabled():
        try:
            rows = supabase_select(table_name, select="id", limit=5000)
            return len(rows)
        except Exception:
            pass
    with get_lock():
        c = get_conn()
        try:
            row = c.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0
        finally:
            c.close()


def db_status_snapshot() -> Dict[str, Any]:
    sb = supabase_enabled()
    return {
        "backend_mode": "supabase_primary" if sb else "local_sqlite",
        "supabase_ok": sb,
        "postgres_dsn_configured": sb,
        "active_write_adapter": "supabase+sqlite-fallback" if sb else "local-sqlite",
        "db_path": str(DB_PATH),
    }
