"""知識庫匯出為 Markdown ZIP（對應原 Streamlit export_notes_to_zip）"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Any, Dict, List


def _fix_content(text: Any) -> str:
    if text is None:
        return ""
    return str(text).strip()


def row_to_markdown(row: Dict[str, Any]) -> str:
    return f"""# {row.get("word", "")}

## 定義
{_fix_content(row.get("definition", ""))}

## 本質
{_fix_content(row.get("meaning", ""))}

## 核心原理
{_fix_content(row.get("roots", ""))}

## 邏輯拆解
{_fix_content(row.get("breakdown", ""))}

## 應用
{_fix_content(row.get("example", ""))}

## 專家理解
{_fix_content(row.get("native_vibe", ""))}

## 相似概念
{_fix_content(row.get("synonym_nuance", ""))}

## 注意
{_fix_content(row.get("usage_warning", ""))}

## 記憶
{_fix_content(row.get("memory_hook", ""))}

## 詞源
{_fix_content(row.get("phonetic", ""))}
"""


def knowledge_rows_to_zip_bytes(rows: List[Dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            word = str(row.get("word", "")).strip()
            if not word:
                continue
            cat = str(row.get("category", "其他") or "其他").split("+")[0].strip()
            cat = re.sub(r'[<>:"/\\\\|?*]', "_", cat)
            wsafe = re.sub(r'[<>:"/\\\\|?*]', "_", word)
            md = row_to_markdown(row)
            zf.writestr(f"知識/{cat}/{wsafe}/note.md", md.encode("utf-8"))
    buf.seek(0)
    return buf.read()
