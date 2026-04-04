#!/usr/bin/env python3
"""
自動流程：Etymonline 抓取 → CSV → 匯入 backend/local.db 的 knowledge。

專案根目錄執行：

  # 從清單增量抓取並寫入本機庫（建議）
  python3 scripts/sync_etymonline_to_knowledge.py --words-file data/etymonline_wordlist.txt

  # 臨時幾個字
  python3 scripts/sync_etymonline_to_knowledge.py --word hello --word world

  # 只重新匯入既有 CSV（不連網）
  python3 scripts/sync_etymonline_to_knowledge.py --import-only

  # 只抓取、不寫 DB
  python3 scripts/sync_etymonline_to_knowledge.py --words-file words.txt --fetch-only

子程序呼叫 fetch_etymonline_raw.py、etymonline_raw_to_local_knowledge.py，行為與旗標與兩者一致。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_FETCH = _ROOT / "scripts" / "fetch_etymonline_raw.py"
_IMPORT = _ROOT / "scripts" / "etymonline_raw_to_local_knowledge.py"
_DEFAULT_CSV = _ROOT / "data" / "etymonline_raw.csv"


def _run(argv: list[str]) -> int:
    p = subprocess.run(argv, cwd=str(_ROOT))
    return int(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="Etymonline 抓取 + 匯入本機 knowledge")
    ap.add_argument("--words-file", default="", help="單字清單（每行一字，# 開頭為註解）")
    ap.add_argument("--word", action="append", default=[], help="單字（可重複；與 --words-file 可併用）")
    ap.add_argument("--csv", default=str(_DEFAULT_CSV), help="CSV 路徑（預設 data/etymonline_raw.csv）")
    ap.add_argument(
        "--no-append",
        action="store_true",
        help="抓取時覆寫 CSV（預設為 --append 增量、跳過已存在 word）",
    )
    ap.add_argument("--delay-ms", type=int, default=600, help="抓取請求間隔（毫秒）")
    ap.add_argument("--timeout", type=int, default=25, help="單次 HTTP 逾時（秒）")
    ap.add_argument("--insecure-ssl", action="store_true", help="略過 SSL 驗證（僅排錯）")
    ap.add_argument(
        "--merge-empty",
        action="store_true",
        help="匯入時僅補齊 knowledge 既有列的空白欄位",
    )
    ap.add_argument("--import-limit", type=int, default=0, help="匯入最多處理 CSV 列數（0=不限）")
    ap.add_argument("--fetch-only", action="store_true", help="只執行抓取")
    ap.add_argument("--import-only", action="store_true", help="只執行 CSV→SQLite")
    args = ap.parse_args()

    if args.fetch_only and args.import_only:
        print("不可同時使用 --fetch-only 與 --import-only", file=sys.stderr)
        return 1

    py = sys.executable
    do_fetch = not args.import_only
    do_import = not args.fetch_only

    if do_fetch:
        if not args.words_file and not args.word:
            print("抓取階段需要 --words-file 和/或 --word", file=sys.stderr)
            return 1
        fcmd = [
            py,
            str(_FETCH),
            "--out",
            args.csv,
            "--delay-ms",
            str(args.delay_ms),
            "--timeout",
            str(args.timeout),
        ]
        if not args.no_append:
            fcmd.append("--append")
        if args.insecure_ssl:
            fcmd.append("--insecure-ssl")
        for w in args.word:
            fcmd.extend(["--word", w])
        if args.words_file:
            fcmd.extend(["--words-file", args.words_file])

        rc = _run(fcmd)
        if rc != 0:
            return rc

    if do_import:
        icmd = [py, str(_IMPORT), "--csv", args.csv]
        if args.merge_empty:
            icmd.append("--merge-empty")
        if args.import_limit > 0:
            icmd.extend(["--limit", str(args.import_limit)])
        rc = _run(icmd)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
