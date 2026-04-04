"""KnowledgeCard Pydantic schema 驗證。"""
import pytest
from pydantic import ValidationError

from backend.schemas import KnowledgeCard


def test_valid_card():
    card = KnowledgeCard(
        word="熵增定律",
        category="物理科學",
        roots="dS >= 0",
        breakdown="步驟一\\n步驟二\\n步驟三",
        definition="熱力學第二定律的一種表述",
        meaning="封閉系統的熵只增不減",
        native_vibe="宇宙傾向於無序",
        example="冰塊融化",
        synonym_nuance="與無序度相關但不同於亂度",
        usage_warning="僅適用於孤立系統",
        memory_hook="房間不整理只會越來越亂",
        phonetic="shāng zēng dìng lǜ",
    )
    assert card.word == "熵增定律"


def test_missing_required_field():
    with pytest.raises(ValidationError):
        KnowledgeCard(category="物理科學")  # type: ignore[call-arg]
