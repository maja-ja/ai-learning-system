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


ContributionMode = Literal["private_use", "named_contribution"]
LearningAttemptSource = Literal["lab", "exam", "knowledge", "handout", "other"]


class ClickEventItem(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    action_label: str = Field(default="", max_length=200)
    page: str = Field(default="", max_length=100)
    seq: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClickEventsBatchBody(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    tenant_id: Optional[str] = None
    profile_id: Optional[str] = None
    events: List[ClickEventItem] = Field(default_factory=list, max_length=500)
