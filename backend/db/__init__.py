"""拆分後的資料庫模組 — 向後相容 re-export。

所有原本 `from backend.database import X` 的程式碼不需改動；
新程式碼建議直接 import 子模組，如 `from backend.db.knowledge import knowledge_list`。
"""

from backend.db.connection import (
    DB_PATH,
    KNOWLEDGE_COLS,
    init_schema,
)
from backend.db.supabase_client import (
    supabase_enabled,
    supabase_rpc,
)
from backend.db.knowledge import (
    knowledge_delete_all,
    knowledge_list,
    knowledge_sync_to_supabase,
    knowledge_upsert,
)
from backend.db.notes import (
    notes_create,
    notes_delete,
    notes_list,
    notes_update,
)
from backend.db.member_storage import (
    member_storage_create,
    member_storage_delete,
    member_storage_list,
)
from backend.db.learner import (
    learner_context_get,
    learner_context_upsert,
)
from backend.db.aha import (
    aha_event_insert,
    aha_event_update_variant,
    aha_events_insert_batch,
    aha_events_needing_variant,
    aha_hook_effectiveness_get,
    aha_hook_upsert,
    aha_hooks_get_active,
    aha_hooks_get_by_ids,
)
from backend.db.attempts import (
    learning_attempt_create,
    learning_attempt_update,
)
from backend.db.tracking import (
    click_events_insert_batch,
    click_markov_predict,
    click_recent_actions,
)
from backend.db.admin import (
    db_status_snapshot,
    table_count,
)

__all__ = [
    "DB_PATH",
    "KNOWLEDGE_COLS",
    "init_schema",
    "supabase_enabled",
    "supabase_rpc",
    "knowledge_list",
    "knowledge_upsert",
    "knowledge_sync_to_supabase",
    "knowledge_delete_all",
    "notes_list",
    "notes_create",
    "notes_update",
    "notes_delete",
    "member_storage_create",
    "member_storage_list",
    "member_storage_delete",
    "learner_context_upsert",
    "learner_context_get",
    "aha_hooks_get_active",
    "aha_hooks_get_by_ids",
    "aha_hook_upsert",
    "aha_hook_effectiveness_get",
    "aha_event_insert",
    "aha_events_insert_batch",
    "aha_events_needing_variant",
    "aha_event_update_variant",
    "learning_attempt_create",
    "learning_attempt_update",
    "click_events_insert_batch",
    "click_recent_actions",
    "click_markov_predict",
    "table_count",
    "db_status_snapshot",
]
