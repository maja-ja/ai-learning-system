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


def _decode_gemini(note_text: str, tier: str = "quality") -> Dict[str, str]:
    if not GEMINI_API_KEY:
        raise ValueError("未設定 GEMINI_API_KEY，無法使用 Gemini")
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"將此筆記轉化為深度知識卡：\n{note_text}"
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
    user_prompt = f"""將以下筆記轉成一張「深度知識卡」，只輸出**一個** JSON 物件，不要其他說明、不要 markdown 包圍。
欄位與語意如下（全部必填，可為空字串）：
{schema_hint}

使用者筆記：
---
{note_text}
---
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


def decode_to_knowledge_card(note_text: str) -> Tuple[Dict[str, str], str]:
    """
    回傳 (知識卡 dict, 使用的供應商代碼 'gemini' | 'claude')
    """
    provider = resolve_ai_provider(tier="quality")
    if provider == "claude":
        return _decode_claude(note_text, tier="quality"), "claude"
    return _decode_gemini(note_text, tier="quality"), "gemini"
