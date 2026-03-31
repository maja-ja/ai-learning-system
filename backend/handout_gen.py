"""
講義 AI 生成（原 Streamlit handout_ai_generate），使用 Gemini；可附參考圖。
"""
from __future__ import annotations

import io
import os
import re
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image
from .model_router import resolve_gemini_model

SYSTEM_PROMPT = """
Role: 專業教材架構師 (Educational Content Architect).
Task: 將原始素材轉化為結構嚴謹、排版精美的 A4 講義。

【⚠️ 輸出禁令】：
- 禁止任何開場白與結尾（如「好的」「希望對你有幫助」）。
- 第一個字必須是講義標題（# 標題）。

【📐 排版】：
1. 主標題 #，章節 ##，重點 ###。
2. 行內公式用單個 $，區塊公式用 $$。
3. 長文可在章節末插入 [換頁]。
4. 列表用 - 或 1.。

語氣：學術、客觀、精確。
"""


def generate_handout_markdown(
    manual_input: str,
    instruction: str = "",
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("講義生成需設定 GEMINI_API_KEY")

    parts: list = [SYSTEM_PROMPT]
    if manual_input:
        parts.append(f"【原始素材】：\n{manual_input}")
    if instruction:
        parts.append(f"【排版要求】：{instruction}")

    if image_bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            parts.append(img)
        except Exception as e:
            raise ValueError(f"圖片無法讀取: {e}") from e

    client = genai.Client(api_key=key)
    # handout explanation quality should prefer quality tier
    model = resolve_gemini_model(tier="quality")
    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=4096,
        ),
    )
    if not response or not response.text:
        raise RuntimeError("模型未回傳內容")

    text = response.text.strip()
    text = re.sub(r"^```markdown\s*|\s*```$", "", text, flags=re.MULTILINE)
    return text
