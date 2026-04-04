"""
跨領域批量解碼（原 Streamlit ai_decode_and_save 邏輯）— 目前使用 Gemini JSON 模式。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from .schemas import KnowledgeCard
from .model_router import resolve_gemini_model
from .prompts_prod import build_decode_system_prompt, build_random_topics_prompt, decode_user_message

CORE_COLS = list(KnowledgeCard.model_fields.keys())


def decode_interdisciplinary(
    input_text: str,
    primary_cat: str,
    aux_cats: Optional[List[str]] = None,
    user_key: str = "",
) -> Optional[Dict[str, str]]:
    aux_cats = aux_cats or []
    key = user_key.strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("請在頁面上方設定您的 Gemini API Key")

    combined_cats = " + ".join([primary_cat] + list(aux_cats))

    system_prompt = build_decode_system_prompt(primary_cat, aux_cats)
    final_prompt = f"{system_prompt}\n\n{decode_user_message(input_text.strip())}"
    client = genai.Client(api_key=key)
    model = resolve_gemini_model(tier="quality")

    response = client.models.generate_content(
        model=model,
        contents=final_prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=2048,
            response_mime_type="application/json",
            response_schema=KnowledgeCard,
        ),
    )

    if not response or not response.text:
        return None

    raw = response.text.strip()
    clean = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE)
    try:
        parsed = json.loads(clean, strict=False)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(clean.replace("\n", "\\n"), strict=False)
        except json.JSONDecodeError:
            return None

    out: Dict[str, str] = {}
    for col in CORE_COLS:
        v = parsed.get(col, "無")
        out[col] = "" if v is None else str(v)
    out["word"] = input_text.strip()
    out["category"] = combined_cats
    return out


def suggest_topics(
    primary_cat: str, aux_cats: Optional[List[str]] = None, count: int = 5, user_key: str = "",
) -> str:
    key = user_key.strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("請在頁面上方設定您的 Gemini API Key")
    aux_cats = aux_cats or []
    prompt = build_random_topics_prompt(primary_cat, aux_cats, count)
    client = genai.Client(api_key=key)
    # topic suggestion can use lower-cost tier model
    model = resolve_gemini_model(tier="cheap")
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=512,
        ),
    )
    if not response or not response.text:
        return ""
    return response.text.replace("*", "").replace("-", "").strip()
