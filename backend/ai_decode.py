"""
知識卡解碼：支援 Google Gemini 與 Anthropic Claude（環境變數 AI_PROVIDER）。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Tuple

from google import genai
from google.genai import types

from .schemas import KnowledgeCard
from .model_router import resolve_provider, resolve_gemini_model, resolve_claude_model
from .prompts_prod import KNOWLEDGE_CARD_FROM_NOTE, knowledge_card_user_message

CARD_KEYS = list(KnowledgeCard.model_fields.keys())

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()


def _normalize_card(raw: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k in CARD_KEYS:
        v = raw.get(k, "")
        if v is None:
            v = ""
        out[k] = str(v).strip()
    return out


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    t = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", t, re.DOTALL | re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    return json.loads(t)


def _decode_gemini(note_text: str, tier: str = "quality", user_key: str = "") -> Dict[str, str]:
    key = user_key.strip() or GEMINI_API_KEY
    if not key:
        raise ValueError("請在頁面上方設定您的 Gemini API Key")
    client = genai.Client(api_key=key)
    prompt = (
        f"{KNOWLEDGE_CARD_FROM_NOTE}\n\n{knowledge_card_user_message(note_text.strip())}"
    )
    response = client.models.generate_content(
        model=resolve_gemini_model(tier=tier),  # explanation tasks use quality tier by default
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=KnowledgeCard,
        ),
    )
    parsed = json.loads(response.text)
    return _normalize_card(parsed)


def _decode_claude(note_text: str, tier: str = "quality") -> Dict[str, str]:
    if not ANTHROPIC_API_KEY:
        raise ValueError("未設定 ANTHROPIC_API_KEY，無法使用 Claude")
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("請安裝 anthropic：pip install anthropic") from e

    schema_hint = "\n".join(
        f'  "{k}": string,  // {KnowledgeCard.model_fields[k].description}'
        for k in CARD_KEYS
    )
    user_prompt = f"""{KNOWLEDGE_CARD_FROM_NOTE}

欄位鍵名與語意（全部鍵須出現；值可為空字串）：
{schema_hint}

{knowledge_card_user_message(note_text.strip())}
"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=resolve_claude_model(tier=tier),
        max_tokens=4096,
        temperature=0.2,
        messages=[{"role": "user", "content": user_prompt}],
    )
    block = msg.content[0]
    if block.type != "text":
        raise ValueError("Claude 回應非文字")
    parsed = _extract_json_from_text(block.text)
    return _normalize_card(parsed)


def resolve_ai_provider(tier: str = "quality") -> str:
    """
    AI_PROVIDER:
      - gemini | google：固定 Gemini
      - claude | anthropic：固定 Claude
      - auto（預設）：有 ANTHROPIC_API_KEY 則 Claude，否則 Gemini
    """
    return resolve_provider(tier=tier)


def decode_to_knowledge_card(
    note_text: str, user_gemini_key: str = "",
) -> Tuple[Dict[str, str], str]:
    provider = resolve_ai_provider(tier="quality")
    if provider == "claude":
        return _decode_claude(note_text, tier="quality"), "claude"
    return _decode_gemini(note_text, tier="quality", user_key=user_gemini_key), "gemini"
