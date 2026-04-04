#!/usr/bin/env python3
"""
抓取 Etymonline 單字頁，保存「原始資料基底」CSV。

重點：
- 只做硬查找（word -> 網頁）
- 保存原始 HTML 摘要與純文字內容，作為後續生成唯一基底
- 不接受提示詞，不做自由語意查詢

用法：
  python3 scripts/fetch_etymonline_raw.py --word hello
  python3 scripts/fetch_etymonline_raw.py --words-file words.txt --out data/etymonline_raw.csv
  python3 scripts/fetch_etymonline_raw.py --words-file words.txt --append --delay-ms 600
"""

from __future__ import annotations

import argparse
import csv
import re
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]

USER_AGENT = "Mozilla/5.0 (compatible; ai-learning-system/1.0)"
DEFAULT_TIMEOUT = 25

CSV_COLUMNS = [
    "word",
    "url",
    "status",
    "http_status",
    "fetched_at",
    "title",
    "origin_and_history",
    "entries_linking_to",
    "raw_text",
    "raw_html_excerpt",
    "error",
]


@dataclass
class FetchResult:
    word: str
    url: str
    status: str
    http_status: int
    fetched_at: str
    title: str
    origin_and_history: str
    entries_linking_to: str
    raw_text: str
    raw_html_excerpt: str
    error: str

    def to_row(self) -> dict[str, str | int]:
        return {
            "word": self.word,
            "url": self.url,
            "status": self.status,
            "http_status": self.http_status,
            "fetched_at": self.fetched_at,
            "title": self.title,
            "origin_and_history": self.origin_and_history,
            "entries_linking_to": self.entries_linking_to,
            "raw_text": self.raw_text,
            "raw_html_excerpt": self.raw_html_excerpt,
            "error": self.error,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_word(raw: str) -> str:
    w = raw.strip()
    if not w:
        return ""
    # 僅允許單字查找必要字符，避免注入式內容
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9\- '\.]{0,63}", w):
        return ""
    return w


def load_words(inline_words: list[str], words_file: str) -> list[str]:
    items: list[str] = []
    for w in inline_words:
        if "," in w:
            items.extend([x for x in w.split(",") if x.strip()])
        else:
            items.append(w)

    if words_file:
        fp = Path(words_file)
        if not fp.is_file():
            raise FileNotFoundError(f"找不到 words file: {fp}")
        for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            items.append(s)

    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        w = normalize_word(raw)
        if not w:
            continue
        key = w.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def _fetch_via_urllib(url: str, timeout: int, insecure_ssl: bool) -> tuple[str, int]:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context() if insecure_ssl else None
    with request.urlopen(req, timeout=timeout, context=context) as resp:
        status = int(getattr(resp, "status", 200))
        html = resp.read().decode("utf-8", "replace")
        return html, status


def _fetch_via_curl(url: str, timeout: int, insecure_ssl: bool) -> tuple[str, int]:
    cmd = ["curl", "-sSL", "-A", USER_AGENT, "--max-time", str(timeout), url]
    if insecure_ssl:
        cmd.insert(1, "-k")
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"curl 失敗 (exit={p.returncode}): {p.stderr.strip()[:300]}")
    # curl -sS 無法直接拿到 HTTP status，這裡視為 200（若 404 通常內容仍可被標記 not_found）
    return p.stdout, 200


def fetch_html(url: str, timeout: int, insecure_ssl: bool) -> tuple[str, int]:
    try:
        return _fetch_via_urllib(url, timeout=timeout, insecure_ssl=insecure_ssl)
    except (error.URLError, TimeoutError, ssl.SSLError, ValueError):
        return _fetch_via_curl(url, timeout=timeout, insecure_ssl=insecure_ssl)


def strip_tags(html: str) -> str:
    # 移除 script/style，避免污染純文字基底
    no_script = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    no_style = re.sub(r"<style\b[^>]*>.*?</style>", " ", no_script, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", no_style)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _capture_section(text: str, start_pat: str, end_pat: str) -> str:
    m = re.search(start_pat, text, flags=re.I)
    if not m:
        return ""
    start = m.end()
    m2 = re.search(end_pat, text[start:], flags=re.I)
    end = (start + m2.start()) if m2 else len(text)
    return text[start:end].strip()


def extract_fields(html: str) -> tuple[str, str, str, str]:
    title = ""
    mt = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    if mt:
        title = re.sub(r"\s+", " ", unescape(mt.group(1))).strip()

    raw_text = strip_tags(html)
    origin = _capture_section(
        raw_text,
        r"\bOrigin and history of\b",
        r"\bEntries linking to\b",
    )
    linking = _capture_section(
        raw_text,
        r"\bEntries linking to\b",
        r"\bMore to explore\b|\bShare\b|\bTrending\b",
    )
    return title, origin, linking, raw_text


def looks_not_found(html: str, text: str) -> bool:
    checks = [
        "not found",
        "no results found",
        "we can't find",
        "search etymonline",
    ]
    blob = (html[:20000] + " " + text[:20000]).lower()
    return any(k in blob for k in checks)


def build_word_url(word: str) -> str:
    return f"https://www.etymonline.com/word/{parse.quote(word)}"


def fetch_word(word: str, timeout: int, insecure_ssl: bool) -> FetchResult:
    url = build_word_url(word)
    fetched_at = now_iso()
    try:
        html, status_code = fetch_html(url, timeout=timeout, insecure_ssl=insecure_ssl)
        title, origin, linking, raw_text = extract_fields(html)
        status = "ok"
        err = ""
        if looks_not_found(html, raw_text):
            status = "not_found"
        if status_code >= 400:
            status = "http_error"
        if not title and not raw_text:
            status = "parse_empty"
        return FetchResult(
            word=word,
            url=url,
            status=status,
            http_status=status_code,
            fetched_at=fetched_at,
            title=title,
            origin_and_history=origin,
            entries_linking_to=linking,
            raw_text=raw_text[:50000],
            raw_html_excerpt=html[:5000],
            error=err,
        )
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            word=word,
            url=url,
            status="error",
            http_status=0,
            fetched_at=fetched_at,
            title="",
            origin_and_history="",
            entries_linking_to="",
            raw_text="",
            raw_html_excerpt="",
            error=f"{e.__class__.__name__}: {e}",
        )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_rows(path: Path, rows: Iterable[FetchResult], append: bool) -> tuple[int, int]:
    ensure_parent(path)
    existing_words: set[str] = set()
    if path.is_file():
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                w = (r.get("word") or "").strip().lower()
                if w:
                    existing_words.add(w)

    mode = "a" if append and path.is_file() else "w"
    wrote = 0
    skipped = 0
    with path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if mode == "w":
            writer.writeheader()
        for row in rows:
            key = row.word.lower()
            if key in existing_words and append:
                skipped += 1
                continue
            writer.writerow(row.to_row())
            wrote += 1
            existing_words.add(key)
    return wrote, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取 Etymonline 原始資料 CSV")
    ap.add_argument("--word", action="append", default=[], help="單字（可重複傳入，或用逗號分隔）")
    ap.add_argument("--words-file", default="", help="單字清單檔（每行一個 word）")
    ap.add_argument("--out", default=str(ROOT / "data" / "etymonline_raw.csv"), help="輸出 CSV")
    ap.add_argument("--append", action="store_true", help="附加寫入，且跳過已存在 word")
    ap.add_argument("--delay-ms", type=int, default=300, help="每個請求之間延遲毫秒")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="請求超時秒數")
    ap.add_argument("--insecure-ssl", action="store_true", help="關閉 SSL 憑證驗證（僅排錯用）")
    args = ap.parse_args()

    try:
        words = load_words(args.word, args.words_file)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    if not words:
        print("沒有可抓取的合法單字（請用 --word 或 --words-file）", file=sys.stderr)
        return 1

    print(f"準備抓取 {len(words)} 個單字...")
    rows: list[FetchResult] = []
    for idx, w in enumerate(words, start=1):
        row = fetch_word(w, timeout=args.timeout, insecure_ssl=args.insecure_ssl)
        rows.append(row)
        print(f"[{idx}/{len(words)}] {w} -> {row.status} ({row.http_status})")
        if idx < len(words) and args.delay_ms > 0:
            time.sleep(args.delay_ms / 1000.0)

    out_path = Path(args.out)
    wrote, skipped = write_rows(out_path, rows, append=args.append)
    print(f"已寫入: {wrote} 筆, 跳過: {skipped} 筆 -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
