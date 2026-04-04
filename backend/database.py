"""向後相容層 — 所有邏輯已遷移至 backend/db/ 子模組。

現有程式碼的 `from . import database as db` 或 `from .database import X`
仍可正常運作；新程式碼請直接 import backend.db。
"""

# Re-export everything from the new db package
from backend.db import *  # noqa: F401, F403
from backend.db import (  # explicit re-exports for type checkers
    DB_PATH,
    KNOWLEDGE_COLS,
    aha_event_insert,
    aha_event_update_variant,
    aha_events_insert_batch,
    aha_events_needing_variant,
    aha_hook_effectiveness_get,
    aha_hook_upsert,
    aha_hooks_get_active,
    aha_hooks_get_by_ids,
    click_events_insert_batch,
    click_markov_predict,
    click_recent_actions,
    db_status_snapshot,
    init_schema,
    knowledge_delete_all,
    knowledge_list,
    knowledge_sync_to_supabase,
    knowledge_upsert,
    learner_context_get,
    learner_context_upsert,
    learning_attempt_create,
    learning_attempt_update,
    member_storage_create,
    member_storage_delete,
    member_storage_list,
    notes_create,
    notes_delete,
    notes_list,
    notes_update,
    supabase_enabled,
    supabase_rpc,
    table_count,
)
