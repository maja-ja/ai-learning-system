"""共用 Pydantic 模型（避免 api 與 ai_decode 循環引用）"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any


class KnowledgeCard(BaseModel):
    word: str = Field(description="核心概念名稱")
    category: str = Field(description="領域分類")
    roots: str = Field(description="底層邏輯或公式")
    breakdown: str = Field(description="結構拆解")
    definition: str = Field(description="直覺定義")
    meaning: str = Field(description="本質意義")
    native_vibe: str = Field(description="專家心法")
    example: str = Field(description="應用實例")
    synonym_nuance: str = Field(description="相似辨析")
    usage_warning: str = Field(description="使用誤區")
    memory_hook: str = Field(description="記憶金句")
    phonetic: str = Field(description="音標或詞源")


AgeBand = Literal["under_13", "13_15", "16_18", "19_22", "23_plus"]
HookType = Literal[
    "analogy",
    "story",
    "visual",
    "misconception_fix",
    "exam_shortcut",
    "cold_fact",
    "counterexample",
    "interactive_sim",
]
AhaEventType = Literal[
    "confused",
    "hint_shown",
    "aha_reported",
    "question_answered",
    "question_corrected",
    "review_passed",
]


class LearnerContextUpsertBody(BaseModel):
    tenant_id: str
    profile_id: str
    age_band: AgeBand
    region_code: str = Field(min_length=2, max_length=32)
    preferred_language: str = Field(default="zh-TW", min_length=2, max_length=16)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AhaHookRecommendQuery(BaseModel):
    tenant_id: str
    profile_id: str
    topic_key: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=5, ge=1, le=20)


class AhaEventIngestBody(BaseModel):
    tenant_id: str
    profile_id: str
    attempt_id: Optional[str] = None
    event_type: AhaEventType
    topic_key: str = Field(min_length=1, max_length=120)
    question_id: Optional[str] = None
    hook_id: Optional[str] = None
    hook_variant_id: Optional[str] = Field(default=None, max_length=120)
    self_report_delta: Optional[int] = Field(default=None, ge=-5, le=5)
    latency_ms: Optional[int] = Field(default=None, ge=0)
    is_correct: Optional[bool] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AhaEventBatchIngestBody(BaseModel):
    events: List[AhaEventIngestBody] = Field(default_factory=list, max_length=200)


class MaintenanceBackfillVariantBody(BaseModel):
    tenant_id: Optional[str] = None
    limit: int = Field(default=500, ge=1, le=5000)
    dry_run: bool = True


class ClickEventItem(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    action_label: str = Field(default="", max_length=200)
    page: str = Field(default="", max_length=100)
    seq: int = Field(default=0, ge=0)


class ClickEventsBatchBody(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    events: List[ClickEventItem] = Field(default_factory=list, max_length=500)
