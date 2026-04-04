#!/usr/bin/env python3
"""
本機排查：服務埠 + web/kadusella .env.local 是否像真值（不印出 secret）。
用法：專案根目錄執行  python3 scripts/check_membership_env.py
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BAD_VALUE_HINTS = (
    "你的值",
    "之後再填",
    "placeholder",
    "xxx",
    "changeme",
)


def load_dotenv_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def looks_placeholder(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    for hint in BAD_VALUE_HINTS:
        if hint.lower() in v.lower():
            return True
    return False


def check_port(label: str, url: str, expect_status: int | None = None) -> str:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            code = r.status
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return f"FAIL 無法連線 ({e.__class__.__name__})"
    if expect_status is not None and code != expect_status:
        return f"WARN HTTP {code}（預期 {expect_status}）"
    return f"OK HTTP {code}"


def main() -> int:
    print("=== 服務埠（本機）===\n")
    print(f"FastAPI   :8000  /health  → {check_port('api', 'http://127.0.0.1:8000/health', 200)}")
    print(f"Next.js   :3000  /        → {check_port('kad', 'http://127.0.0.1:3000/', None)}")
    print(f"Vite web  :5173  /        → {check_port('web', 'http://127.0.0.1:5173/', None)}")
    print()

    web_env = load_dotenv_file(ROOT / "web" / ".env.local")
    kad_env = load_dotenv_file(ROOT / "kadusella" / ".env.local")

    print("=== web/.env.local ===\n")
    if not web_env:
        print("（檔案不存在或為空）\n")
    else:
        pk = web_env.get("VITE_CLERK_PUBLISHABLE_KEY", "") or web_env.get(
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", ""
        )
        bill = web_env.get("VITE_BILLING_BASE_URL", "")
        api = web_env.get("VITE_API_BASE_URL", "")

        def stat(ok: bool, msg: str) -> str:
            return ("OK  " if ok else "BAD ") + msg

        print(
            stat(
                bool(pk) and not looks_placeholder(pk) and pk.startswith("pk_"),
                "VITE_CLERK_PUBLISHABLE_KEY（或誤用 NEXT_PUBLIC_，Vite 只吃 VITE_）",
            )
        )
        print(stat(bool(bill) and bill.startswith("http"), "VITE_BILLING_BASE_URL"))
        print(stat(True, f"VITE_API_BASE_URL（可選）{'已設' if api else '未設，走 Vite proxy'}"))
        if "CLERK_SECRET_KEY" in web_env:
            print("BAD  web 不應含 CLERK_SECRET_KEY（請刪除，只放 kadusella）")
        if web_env.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY") and not web_env.get(
            "VITE_CLERK_PUBLISHABLE_KEY"
        ):
            print("BAD  僅有 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY：請改名為 VITE_CLERK_PUBLISHABLE_KEY")
        print()

    print("=== kadusella/.env.local ===\n")
    if not kad_env:
        print("（檔案不存在或為空）\n")
    else:
        sup_url = kad_env.get("SUPABASE_URL", "")
        sup_key = kad_env.get("SUPABASE_SERVICE_ROLE_KEY", "")
        ck_pub = kad_env.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")
        ck_sec = kad_env.get("CLERK_SECRET_KEY", "")
        tok = kad_env.get("MEMBERSHIP_TOKEN_SECRET", "")
        bill = kad_env.get("NEXT_PUBLIC_BILLING_BASE_URL", "")

        print(
            ("OK  " if re.match(r"^https://.+\..+", sup_url or "") else "BAD ")
            + "SUPABASE_URL（需 https://…）"
        )
        print(
            ("OK  " if len(sup_key) >= 32 and not sup_key.isspace() else "BAD ")
            + "SUPABASE_SERVICE_ROLE_KEY（長度與格式）"
        )
        if looks_placeholder(sup_url) or looks_placeholder(sup_key):
            print("BAD  Supabase 變數仍像占位字串")

        print(
            ("OK  " if ck_pub.startswith("pk_") and not looks_placeholder(ck_pub) else "BAD ")
            + "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"
        )
        print(
            ("OK  " if ck_sec.startswith("sk_") and not looks_placeholder(ck_sec) else "BAD ")
            + "CLERK_SECRET_KEY（不會顯示內容）"
        )
        print(("OK  " if len(tok) >= 32 else "BAD ") + "MEMBERSHIP_TOKEN_SECRET 長度")
        print(("OK  " if bill.startswith("http") else "BAD ") + "NEXT_PUBLIC_BILLING_BASE_URL")
        print()

    print("=== 建議下一步 ===\n")
    print("1. 三個服務都 OK：backend :8000、kadusella :3000、web :5173")
    print("2. 填真實 Supabase URL + service_role key，並套用 migrations")
    print("3. Clerk publishable/secret 成對且非占位")
    print("4. 啟動 backend 的 shell 內：export MEMBERSHIP_TOKEN_SECRET=（與 kadusella 相同）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
