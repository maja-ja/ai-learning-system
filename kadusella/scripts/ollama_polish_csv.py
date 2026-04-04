#!/usr/bin/env python3
"""
在 Mac mini（或其他機器）上：本機 Ollama localhost 讀 CSV → 潤飾／補寫指定欄位 → 輸出新 CSV。

前置：
  1. 安裝並啟動 Ollama：https://ollama.com
  2. 拉模型（16GB 建議 7B 量化）：
       ollama pull qwen2.5:7b

環境變數（可選）：
  OLLAMA_HOST   預設 http://127.0.0.1:11434
  OLLAMA_MODEL  預設 qwen2.5:7b

範例（先試 3 筆）：
  python3 scripts/ollama_polish_csv.py \\
    --in knowledge_rows.csv \\
    --out knowledge_rows_polished.csv \\
    --columns definition,meaning \\
    --limit 3

整批（耗時長，建議 screen/tmux）：
  python3 scripts/ollama_polish_csv.py -i knowledge_rows.csv -o out.csv -c definition,meaning

續跑（略過前 100 筆已寫入的 out，需自行確保 out 與 in 列順序一致時可用 --skip）：
  python3 scripts/ollama_polish_csv.py ... --skip 100
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def ollama_generate(host: str, model: str, prompt: str, timeout: int = 600) -> str:
    url = f"{host.rstrip('/')}/api/generate"
    payload = json.dumps(
        {"model": model, "prompt": prompt, "stream": False},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"無法連線 Ollama ({url})。請確認本機已執行 ollama serve 且模型已拉取。\n{e}"
        ) from e
    return (data.get("response") or "").strip()


def build_prompt(
    instruction: str,
    word: str,
    column: str,
    original: str,
) -> str:
    return f"""{instruction}

【詞條】{word}
【欄位】{column}
【原文】
{original}

請只輸出潤飾後的該欄位正文。禁止前言、結尾寒暄、對話套語；禁止以 Markdown 程式碼區塊包裹；禁止重複輸出欄位名稱標題。"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Ollama localhost 批次潤飾 CSV 欄位")
    ap.add_argument("--in", dest="in_path", required=True, help="輸入 CSV")
    ap.add_argument("--out", dest="out_path", required=True, help="輸出 CSV")
    ap.add_argument(
        "--columns",
        "-c",
        required=True,
        help="要潤飾的欄位，逗號分隔，例如 definition,meaning",
    )
    ap.add_argument(
        "--instruction",
        default=(
            "身分：繁體中文教材編輯（正式出版取向）。"
            "任務：在不改變事實前提下潤飾指定欄位。"
            "要求：用語精準、條理清楚、可讀性適合高中以上；"
            "不得臆測或新增原文未支持之內容；"
            "保留專有名詞、記號與 LaTeX。"
        ),
        help="給模型的任務說明",
    )
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 筆，0=全部")
    ap.add_argument("--skip", type=int, default=0, help="略過前 N 筆（續跑用）")
    ap.add_argument("--delay", type=float, default=0.2, help="每請求間隔秒數，降低發熱")
    ap.add_argument("--timeout", type=int, default=600, help="單次請求逾時秒數")

    args = ap.parse_args()
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    cols = [x.strip() for x in args.columns.split(",") if x.strip()]

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    if not in_path.is_file():
        print(f"找不到輸入：{in_path}", file=sys.stderr)
        return 1

    # 先讀全部列（CSV 含換行欄位時必須一次讀入）
    with in_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("CSV 無表頭", file=sys.stderr)
            return 1
        rows = list(reader)

    for c in cols:
        if c not in fieldnames:
            print(f"欄位不存在於表頭：{c}", file=sys.stderr)
            return 1

    total = len(rows)
    end = total if args.limit <= 0 else min(total, args.limit)
    start = min(args.skip, end)

    print(f"模型={model} host={host}", file=sys.stderr)
    print(f"列數 total={total}，處理範圍 [{start}, {end})", file=sys.stderr)

    processed = 0
    for i in range(start, end):
        row = rows[i]
        word = (row.get("word") or row.get("Word") or f"row{i}").strip()
        for col in cols:
            raw = (row.get(col) or "").strip()
            if not raw:
                continue
            prompt = build_prompt(args.instruction, word, col, raw)
            try:
                new_text = ollama_generate(host, model, prompt, timeout=args.timeout)
                if new_text:
                    row[col] = new_text
            except RuntimeError as e:
                print(f"[錯誤] 第 {i} 列 欄位 {col}: {e}", file=sys.stderr)
                return 1
            processed += 1
            time.sleep(args.delay)
        if (i + 1) % 10 == 0:
            print(f"… 已完成列至 index={i}", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"完成：已寫入 {out_path}（本輪共呼叫潤飾 {processed} 個非空欄位）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
