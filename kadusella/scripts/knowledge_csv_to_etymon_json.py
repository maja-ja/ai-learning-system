#!/usr/bin/env python3
"""
將匯出的 knowledge_rows.csv 轉成符合 public.etymon_entries 的 JSON 陣列
（不含 id / created_at / updated_at；擴充欄位合併進 12 核心文字欄）。

用法：
  export TENANT_ID='你的租戶 uuid'
  python3 scripts/knowledge_csv_to_etymon_json.py
  python3 scripts/knowledge_csv_to_etymon_json.py --csv path/to.csv --out data/etymon-import.json

接著（已設定 .env.local 的 Service Role）：
  npm run sb:upsert -- etymon_entries data/etymon-import.json tenant_id,word
  （若 upsert 不支援複合 onConflict，請改用我們提供的分批 insert 或 SQL）
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

CORE = [
    "word",
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

# 擴充欄 → 合併目標（避免 etymon_entries 缺欄）
EXTRA_TARGETS: list[tuple[str, str, str]] = [
    ("translation", "synonym_nuance", "【翻譯／對照】"),
    ("visual_prompt", "example", "【畫面聯想】"),
    ("social_status", "native_vibe", "【語境／正式度】"),
    ("emotional_tone", "native_vibe", "【情緒基調】"),
    ("street_usage", "native_vibe", "【社群用法】"),
    ("collocation", "example", "【搭配】"),
    ("etymon_story", "breakdown", "【脈絡故事】"),
    ("audio_tag", "memory_hook", "【聲音聯想】"),
]


def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def append_block(base: str, title: str, body: str) -> str:
    body = norm(body)
    if not body:
        return base
    b = norm(base)
    sep = "\n\n" if b else ""
    return f"{b}{sep}{title}\n{body}"


def row_to_etymon(row: dict[str, str], tenant_id: str) -> dict:
    out: dict = {
        "tenant_id": tenant_id,
        "created_by": None,
        "model": "import/knowledge_csv",
        "prompt_version": "csv_migrate_v1",
    }
    for k in CORE:
        out[k] = norm(row.get(k))

    for col, target, title in EXTRA_TARGETS:
        out[target] = append_block(out[target], title, row.get(col))

    term = norm(row.get("term"))
    if term:
        out["phonetic"] = append_block(out["phonetic"], "【term】", term)

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        default=str(Path(__file__).resolve().parents[1] / "knowledge_rows.csv"),
        help="來源 CSV 路徑",
    )
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[1] / "data" / "etymon-import.json"),
        help="輸出 JSON 路徑",
    )
    args = ap.parse_args()

    tenant_id = os.environ.get("TENANT_ID", "").strip()
    if not tenant_id:
        print("請設定環境變數 TENANT_ID（你的 tenants.id uuid）", file=sys.stderr)
        return 1

    src = Path(args.csv)
    if not src.is_file():
        print(f"找不到 CSV：{src}", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows_out: list[dict] = []
    with src.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("CSV 無表頭", file=sys.stderr)
            return 1
        for row in reader:
            if not any(norm(row.get(k)) for k in CORE[:3]):
                continue
            rows_out.append(row_to_etymon(row, tenant_id))

    out_path.write_text(
        json.dumps(rows_out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已寫入 {len(rows_out)} 筆 → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
