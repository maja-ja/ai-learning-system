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

CORE_COLS = list(KnowledgeCard.model_fields.keys())


def decode_interdisciplinary(
    input_text: str,
    primary_cat: str,
    aux_cats: Optional[List[str]] = None,
) -> Optional[Dict[str, str]]:
    aux_cats = aux_cats or []
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("批量解碼需設定 GEMINI_API_KEY（與網頁單筆解碼可並用不同設定）")

    combined_cats = " + ".join([primary_cat] + list(aux_cats))

    system_prompt = f"""
Role: 全領域知識解構專家 (Interdisciplinary Polymath Decoder).
Task: 針對輸入內容進行深度拆解，輸出高品質 JSON。

【核心視角】：
以「{primary_cat}」為框架，揉合「{", ".join(aux_cats) if aux_cats else "通用百科"}」視角進行交叉解碼。

【🚫 絕對禁令】：
- 嚴禁任何開場白或結尾語。直接進入知識點。
- 嚴禁在 JSON 之外輸出任何文字。

【📐 輸出規範】：
1. 必須輸出純 JSON，嚴禁 ```json 標籤。
2. LaTeX 雙重轉義：使用 \\\\frac 等形式。
3. JSON 內換行使用 \\\\n。

【📋 欄位】：word, category, roots, breakdown, definition, meaning, native_vibe,
example, synonym_nuance, usage_warning, memory_hook, phonetic
其中 category 必須為「{combined_cats}」。
"""

    final_prompt = f"{system_prompt}\n\n解碼目標：「{input_text}」"
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


def suggest_topics(primary_cat: str, aux_cats: Optional[List[str]] = None, count: int = 5) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("需設定 GEMINI_API_KEY")
    aux_cats = aux_cats or []
    combined = " + ".join([primary_cat] + list(aux_cats))
    prompt = f"""
你是一位博學的知識策展人。
請針對「{combined}」這個領域組合，推薦 {count} 個具備深度學習價值的「繁體中文」主題或概念。

【絕對要求】：
1. 只輸出主題名稱，每個主題一行。
2. 必須使用繁體中文。
3. 嚴禁開場白、結尾、編號或解釋。
4. 嚴禁 Markdown。
5. 嚴禁標點符號。
"""
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
