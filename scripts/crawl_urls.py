#!/usr/bin/env python3
"""
通用網頁批次抓取（爬蟲）：HTTP(S) URL → 本機 HTML + 純文字 + manifest CSV。

- 僅 http/https；預設遵守 robots.txt（可用 --ignore-robots 關閉，自負風險）。
- 請遵守目標網站服務條款與頻率限制；預設請求間有延遲。

用法（專案根目錄）：

  python3 scripts/crawl_urls.py --url https://example.com/
  python3 scripts/crawl_urls.py --urls-file data/seed_urls.txt --out-dir data/crawl/run1
  python3 scripts/crawl_urls.py --urls-file seeds.txt --follow-depth 1 --max-urls 40 --delay-ms 800

urls 檔：一行一個 URL，# 開頭為註解。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import ssl
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib import error, parse, robotparser, request

ROOT = Path(__file__).resolve().parents[1]
# 請與 robots.txt 檢查使用相同識別字串（取第一個 token）
USER_AGENT = "ai-learning-system-crawl/1.0 (contact: local-dev)"
DEFAULT_TIMEOUT = 25

HREF_RE = re.compile(r"""href\s*=\s*(["'])(.*?)\1""", re.IGNORECASE | re.DOTALL)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_urls(inline: list[str], urls_file: str) -> list[str]:
    items: list[str] = []
    for u in inline:
        u = u.strip()
        if u and not u.startswith("#"):
            items.append(u)
    if urls_file:
        fp = Path(urls_file)
        if not fp.is_file():
            raise FileNotFoundError(f"找不到 urls 檔: {fp}")
        for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            items.append(s)
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        raw = raw.strip()
        p = parse.urlparse(raw)
        if p.scheme not in ("http", "https"):
            continue
        norm = raw.split("#", 1)[0].strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def _fetch_via_urllib(url: str, timeout: int, insecure_ssl: bool) -> tuple[bytes, int]:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context() if insecure_ssl else None
    with request.urlopen(req, timeout=timeout, context=context) as resp:
        status = int(getattr(resp, "status", 200))
        body = resp.read()
        return body, status


def _fetch_via_curl(url: str, timeout: int, insecure_ssl: bool) -> tuple[bytes, int]:
    cmd = ["curl", "-sSL", "-A", USER_AGENT, "--max-time", str(timeout), url]
    if insecure_ssl:
        cmd.insert(1, "-k")
    p = subprocess.run(cmd, capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"curl 失敗 (exit={p.returncode}): {p.stderr.decode('utf-8', 'replace')[:300]}")
    return p.stdout, 200


def fetch_bytes(url: str, timeout: int, insecure_ssl: bool) -> tuple[bytes, int]:
    try:
        return _fetch_via_urllib(url, timeout=timeout, insecure_ssl=insecure_ssl)
    except (error.URLError, TimeoutError, ssl.SSLError, ValueError, OSError):
        return _fetch_via_curl(url, timeout=timeout, insecure_ssl=insecure_ssl)


def strip_tags(html: str) -> str:
    no_script = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    no_style = re.sub(r"<style\b[^>]*>.*?</style>", " ", no_script, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", no_style)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def page_title(html: str) -> str:
    mt = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    if not mt:
        return ""
    return re.sub(r"\s+", " ", unescape(mt.group(1))).strip()


def same_netloc(a: str, b: str) -> bool:
    return parse.urlparse(a).netloc.lower() == parse.urlparse(b).netloc.lower()


def extract_same_host_links(page_url: str, html: str) -> list[str]:
    base = page_url
    out: list[str] = []
    seen: set[str] = set()
    for m in HREF_RE.finditer(html):
        href = (m.group(2) or "").strip()
        if not href or href.startswith("#"):
            continue
        low = href.lower()
        if low.startswith(("javascript:", "mailto:", "tel:", "data:")):
            continue
        full = parse.urljoin(base, href)
        p = parse.urlparse(full)
        if p.scheme not in ("http", "https"):
            continue
        full = full.split("#", 1)[0].strip()
        if not same_netloc(full, page_url):
            continue
        key = full.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(full)
    return out


_robots_cache: dict[str, robotparser.RobotFileParser] = {}


def can_fetch(url: str, respect_robots: bool, timeout: int) -> tuple[bool, str]:
    if not respect_robots:
        return True, "ignored"
    parsed = parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "bad_scheme"
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _robots_cache:
        rp = robotparser.RobotFileParser()
        robots_url = parse.urljoin(origin, "/robots.txt")
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception as e:  # noqa: BLE001
            _robots_cache[origin] = rp
            return True, f"robots_read_error:{e.__class__.__name__}"
        _robots_cache[origin] = rp
    rp = _robots_cache[origin]
    ua = USER_AGENT.split()[0].strip() or "*"
    try:
        ok = rp.can_fetch(ua, url)
    except Exception as e:  # noqa: BLE001
        return True, f"can_fetch_error:{e.__class__.__name__}"
    return ok, "ok" if ok else "disallowed"


def file_slug(url: str, index: int) -> str:
    p = parse.urlparse(url)
    path = (p.path or "/").strip("/").replace("/", "_")[:60]
    if not path or path == "_":
        path = "index"
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", path).strip("_")[:50]
    if not safe:
        safe = "page"
    h = hashlib.sha256(url.encode()).hexdigest()[:10]
    return f"{index:04d}_{safe}_{h}"


@dataclass
class Row:
    url: str
    fetched_at: str
    http_status: int
    robots_note: str
    title: str
    html_path: str
    txt_path: str
    bytes_saved: int
    error: str


def write_manifest(path: Path, rows: Iterable[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "url",
        "fetched_at",
        "http_status",
        "robots_note",
        "title",
        "html_path",
        "txt_path",
        "bytes_saved",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "url": r.url,
                    "fetched_at": r.fetched_at,
                    "http_status": r.http_status,
                    "robots_note": r.robots_note,
                    "title": r.title,
                    "html_path": r.html_path,
                    "txt_path": r.txt_path,
                    "bytes_saved": r.bytes_saved,
                    "error": r.error,
                }
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="通用 HTTP(S) 批次網頁抓取")
    ap.add_argument("--url", action="append", default=[], help="URL（可重複）")
    ap.add_argument("--urls-file", default="", help="一行一個 URL")
    ap.add_argument(
        "--out-dir",
        default="",
        help="輸出目錄（預設 data/crawl/<UTC 時間戳>）",
    )
    ap.add_argument("--delay-ms", type=int, default=500, help="請求之間延遲（毫秒）")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="單次請求逾時（秒）")
    ap.add_argument("--max-bytes", type=int, default=2_000_000, help="單頁 HTML 最多儲存位元組")
    ap.add_argument(
        "--follow-depth",
        type=int,
        default=0,
        help="在同一網域內，自種子頁向外展開的層數（0=只抓種子）",
    )
    ap.add_argument("--max-urls", type=int, default=80, help="最多抓取 URL 數（含種子）")
    ap.add_argument(
        "--ignore-robots",
        action="store_true",
        help="不檢查 robots.txt（可能違反站方規範，請謹慎）",
    )
    ap.add_argument("--insecure-ssl", action="store_true", help="略過 SSL 驗證（僅排錯）")
    args = ap.parse_args()

    try:
        seeds = load_urls(args.url, args.urls_file)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    if not seeds:
        print("沒有有效 URL（需要 http(s) 的 --url 或 --urls-file）", file=sys.stderr)
        return 1

    out_root = Path(args.out_dir) if args.out_dir else ROOT / "data" / "crawl" / now_iso().replace(":", "")
    out_root.mkdir(parents=True, exist_ok=True)
    respect_robots = not args.ignore_robots

    rows: list[Row] = []
    visited: set[str] = set()
    queued: set[str] = {s.lower() for s in seeds}
    q: deque[tuple[str, int]] = deque((u, 0) for u in seeds)
    idx = 0

    while q and len(visited) < args.max_urls:
        url, depth = q.popleft()
        key = url.lower()
        if key in visited:
            continue
        visited.add(key)
        idx += 1

        allowed, robots_note = can_fetch(url, respect_robots, args.timeout)
        fetched_at = now_iso()
        if not allowed:
            rows.append(
                Row(
                    url=url,
                    fetched_at=fetched_at,
                    http_status=0,
                    robots_note=robots_note,
                    title="",
                    html_path="",
                    txt_path="",
                    bytes_saved=0,
                    error="robots_disallow",
                )
            )
            if args.delay_ms > 0 and q:
                time.sleep(args.delay_ms / 1000.0)
            continue

        try:
            body, status = fetch_bytes(url, timeout=args.timeout, insecure_ssl=args.insecure_ssl)
        except Exception as e:  # noqa: BLE001
            rows.append(
                Row(
                    url=url,
                    fetched_at=fetched_at,
                    http_status=0,
                    robots_note=robots_note,
                    title="",
                    html_path="",
                    txt_path="",
                    bytes_saved=0,
                    error=f"{e.__class__.__name__}: {e}",
                )
            )
            if args.delay_ms > 0 and q:
                time.sleep(args.delay_ms / 1000.0)
            continue

        cut = body[: args.max_bytes]
        try:
            html = cut.decode("utf-8", errors="replace")
        except Exception:
            html = cut.decode("latin-1", errors="replace")

        title = page_title(html)
        text = strip_tags(html)
        slug = file_slug(url, idx)
        html_rel = f"{slug}.html"
        txt_rel = f"{slug}.txt"
        html_path = out_root / html_rel
        txt_path = out_root / txt_rel
        html_path.write_bytes(cut)
        txt_path.write_text(text[:500_000], encoding="utf-8", errors="replace")

        rows.append(
            Row(
                url=url,
                fetched_at=fetched_at,
                http_status=status,
                robots_note=robots_note,
                title=title,
                html_path=html_rel,
                txt_path=txt_rel,
                bytes_saved=len(cut),
                error="",
            )
        )

        if depth < args.follow_depth and len(visited) < args.max_urls:
            for link in extract_same_host_links(url, html):
                lk = link.lower()
                if lk in visited or lk in queued:
                    continue
                queued.add(lk)
                q.append((link, depth + 1))

        if args.delay_ms > 0 and q and len(visited) < args.max_urls:
            time.sleep(args.delay_ms / 1000.0)

    manifest_path = out_root / "manifest.csv"
    write_manifest(manifest_path, rows)
    print(f"完成：{len(rows)} 筆 → {out_root}")
    print(f"清單：{manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
