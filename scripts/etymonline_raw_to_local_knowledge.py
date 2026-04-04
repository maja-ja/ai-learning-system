#!/usr/bin/env python3
"""
將 fetch_etymonline_raw.py 產生的 CSV 匯入本機 SQLite knowledge 表。

映射（現階段以「先填空」為主）：
- word / category=詞源
- definition：擷取段落開頭摘要
- breakdown：完整 origin_and_history + 可選 entries_linking_to
- phonetic：來源 URL 與擷取時間（沿用欄位放引用資訊）
- usage_warning：標註來源與查證提醒

用法（專案根目錄）：
  python3 scripts/etymonline_raw_to_local_knowledge.py
  python3 scripts/etymonline_raw_to_local_knowledge.py --csv data/etymonline_raw.csv --merge-empty
  python3 scripts/etymonline_raw_to_local_knowledge.py --limit 50
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend import database as db


def _clean_title(title: str, word: str) -> str:
    t = (title or "").strip()
    for suffix in (" - Etymology, Origin & Meaning", " - Etymology, origin and meaning"):
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
    if t.lower().startswith("etymology of "):
        t = t[13:].strip()
    return t or word


def csv_row_to_knowledge(row: Dict[str, str]) -> Dict[str, Any] | None:
    word = (row.get("word") or "").strip()
    if not word:
        return None
    status = (row.get("status") or "").strip().lower()
    origin = (row.get("origin_and_history") or "").strip()
    linking = (row.get("entries_linking_to") or "").strip()
    url = (row.get("url") or "").strip()
    fetched = (row.get("fetched_at") or "").strip()
    title = _clean_title(row.get("title") or "", word)

    if status != "ok":
        err = (row.get("error") or "").strip()
        breakdown = f"【擷取狀態】{status}\n"
        if err:
            breakdown += f"{err}\n"
        if url:
            breakdown += f"URL: {url}\n"
        return {
            "word": word,
            "category": "詞源",
            "roots": "",
            "breakdown": breakdown.strip(),
            "definition": title,
            "meaning": "此筆無成功擷取詞源正文，請重新抓取或手動補齊。",
            "native_vibe": "",
            "example": "",
            "synonym_nuance": "",
            "usage_warning": f"status={status}。請以 Etymonline 或權威字典複核。",
            "memory_hook": "",
            "phonetic": f"來源: {url}\n擷取: {fetched}" if url else "",
        }

    raw = (row.get("raw_text") or "").strip()
    parts: list[str] = []
    if origin:
        parts.append("【Origin & history】\n" + origin)
    if linking:
        # 常含廣告句尾，仍保留作關聯線索
        parts.append("【Entries linking to】\n" + linking)
    breakdown = "\n\n".join(parts)
    if not breakdown:
        if len(raw) > 80:
            breakdown = "【Raw text（節錄）】\n" + raw[:8000]
        else:
            return None

    summary = (origin[:500] if origin else (raw[:500] if raw else title))
    if len(summary) >= 500:
        summary = summary[:497] + "…"

    return {
        "word": word,
        "category": "詞源",
        "roots": "",
        "breakdown": breakdown,
        "definition": summary if summary else title,
        "meaning": "詞源與歷史敘述見下方拆解。",
        "native_vibe": "",
        "example": "",
        "synonym_nuance": "",
        "usage_warning": "內容來自 Online Etymology Dictionary 頁面擷取，學術細節請交叉查證。",
        "memory_hook": "",
        "phonetic": (f"來源: {url}\n擷取: {fetched}" if url else "").strip(),
    }


def _merge_with_existing(
    incoming: Dict[str, Any],
    existing: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """已有內容的欄位保留；僅在空白時用 CSV 補上。"""
    if not existing:
        return incoming
    text_fields = [
        "category",
        "roots",
        "breakdown",
        "definition",
        "meaning",
        "native_vibe",
        "example",
        "synonym_nuance",
        "usage_warning",
        "memory_hook",
        "phonetic",
    ]
    out: Dict[str, Any] = {"word": incoming["word"]}
    for k in text_fields:
        ex = str(existing.get(k) or "").strip()
        inc = str(incoming.get(k) or "").strip()
        out[k] = ex if ex else inc
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Etymonline CSV → backend/local.db knowledge")
    ap.add_argument(
        "--csv",
        default=str(_ROOT / "data" / "etymonline_raw.csv"),
        help="fetch_etymonline_raw.py 輸出的 CSV",
    )
    ap.add_argument(
        "--merge-empty",
        action="store_true",
        help="若該 word 已存在，只填入目前為空的文字欄位（不覆寫已有內容）",
    )
    ap.add_argument("--limit", type=int, default=0, help="最多處理 N 筆（0=不限制）")
    args = ap.parse_args()

    path = Path(args.csv)
    if not path.is_file():
        print(f"找不到 CSV: {path}", file=sys.stderr)
        return 1

    existing_by_word: Dict[str, Dict[str, Any]] = {}
    if args.merge_empty:
        for row in db.knowledge_list():
            w = str(row.get("word") or "").strip()
            if w:
                existing_by_word[w.lower()] = row

    db.init_schema()
    processed = 0
    upserted = 0
    skipped = 0

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if args.limit and processed >= args.limit:
                break
            processed += 1
            rec = csv_row_to_knowledge(row)
            if rec is None:
                skipped += 1
                continue
            wkey = rec["word"].strip().lower()
            if args.merge_empty and wkey in existing_by_word:
                rec = _merge_with_existing(rec, existing_by_word[wkey])
            db.knowledge_upsert(rec)
            upserted += 1

    print(f"讀取 {processed} 列 CSV，寫入 knowledge {upserted} 筆，略過 {skipped} 筆。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
