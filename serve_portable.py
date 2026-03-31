#!/usr/bin/env python3
"""
單埠上線（任意機器、同一資料夾）：建置 web/dist 後，由 FastAPI 同時提供 SPA + API。
不需 Nginx；Cloudflare Tunnel 只需指到 http://127.0.0.1:<埠>。

環境變數：
  START_API_PORT  預設 8000
  SKIP_WEB_BUILD  設為 1 時略過自動 npm build（已手動建置時）
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def main() -> None:
    root = os.path.abspath(os.path.dirname(__file__))
    web = os.path.join(root, "web")
    dist_index = os.path.join(web, "dist", "index.html")

    if not os.path.isfile(dist_index) and os.getenv("SKIP_WEB_BUILD", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        if not os.path.isdir(web) or not os.path.isfile(os.path.join(web, "package.json")):
            print("❌ 找不到 web/package.json，無法建置前端。")
            sys.exit(1)
        print("📦 建置前端 web/dist …")
        shell = sys.platform == "win32"
        subprocess.check_call(["npm", "ci"], cwd=web, shell=shell)
        subprocess.check_call(["npm", "run", "build"], cwd=web, shell=shell)

    if not os.path.isfile(os.path.join(web, "dist", "index.html")):
        print("❌ 缺少 web/dist/index.html。請執行：cd web && npm run build")
        sys.exit(1)

    os.environ["SERVE_WEB_DIST"] = "1"
    port_s = os.getenv("START_API_PORT", "8000").strip()
    try:
        port = int(port_s)
    except ValueError:
        print(f"❌ START_API_PORT 無效：{port_s!r}")
        sys.exit(1)

    if _port_in_use("127.0.0.1", port):
        print(
            f"❌ 埠 {port} 已被占用（常見：另一個 uvicorn、或 python start.py 仍在跑）。\n"
            f"   查詢：lsof -i :{port} -sTCP:LISTEN\n"
            f"   或改用：START_API_PORT=8001 python serve_portable.py\n"
            "   （若用 Cloudflare Tunnel，請把 config.yml 裡 service 埠改成同一數字。）\n"
        )
        sys.exit(1)

    print(f"🌐 單埠模式  http://127.0.0.1:{port}/  （API 同埠，勿設 VITE_API_BASE_URL）\n")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--proxy-headers",
        "--forwarded-allow-ips=*",
    ]
    subprocess.check_call(cmd, cwd=root)


if __name__ == "__main__":
    main()
