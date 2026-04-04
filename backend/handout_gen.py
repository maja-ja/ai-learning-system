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
from .prompts_prod import HANDOUT_SYSTEM

SYSTEM_PROMPT = HANDOUT_SYSTEM


def generate_handout_markdown(
    manual_input: str,
    instruction: str = "",
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    user_key: str = "",
) -> str:
    key = user_key.strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("請在頁面上方設定您的 Gemini API Key")

    parts: list = [SYSTEM_PROMPT]
    if manual_input:
        parts.append(f"使用者素材：\n{manual_input}")
    if instruction:
        parts.append(f"排版指示：{instruction}")

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
