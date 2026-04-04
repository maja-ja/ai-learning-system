#!/usr/bin/env python3
"""
一鍵啟動：FastAPI :8000 + Vite :5173
環境變數：
  START_API_PORT             後端埠，預設 8000
  START_KNOWLEDGE            知識庫代碼（與下方命令列相同），非互動時使用
  START_DEMO_KNOWLEDGE       同上別名，仍支援純數字
  ALSO_RUN_KADUSELLA_NEXT=true  同時開 kadusella Next（npm run dev，預設 :3000）

知識庫代碼（命令列第一參數或互動輸入）：
  N      先刪舊再寫 N 筆（N 為正整數）
  gN     同上；g0 僅刪舊不寫
  w / w0 僅刪舊不寫
  aN     不刪舊，追加 N 筆
  ?      僅印出代碼規則後照常啟動（不執行知識庫）
  例：python start.py g20　python start.py w0　python start.py ?
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def _wait_api_ready(port: int, seconds: float = 20) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(0.35)
    return False


def _resolve_start_knowledge_cmd(argv: list[str]):
    from backend.knowledge_cmd import KNOWLEDGE_CMD_RULES, parse_knowledge_cmd

    if len(argv) >= 2:
        raw = argv[1].strip()
        if raw == "?":
            print(KNOWLEDGE_CMD_RULES)
            return None
        try:
            return parse_knowledge_cmd(argv[1])
        except ValueError as e:
            print(f"❌ 知識庫指令錯誤：{e}")
            sys.exit(1)
    env_raw = (
        os.getenv("START_KNOWLEDGE", "").strip()
        or os.getenv("START_DEMO_KNOWLEDGE", "").strip()
    )
    if env_raw:
        if env_raw == "?":
            print(KNOWLEDGE_CMD_RULES)
            return None
        try:
            return parse_knowledge_cmd(env_raw)
        except ValueError as e:
            print(f"⚠️ START_KNOWLEDGE 無效（{e}），已略過。")
            return None
    if sys.stdin.isatty():
        print(
            "知識庫代碼： g20 / g 20、w0、a10、純數字 20　? 規則　Enter 略過"
        )
        while True:
            try:
                line = input("指令> ").strip()
            except EOFError:
                return None
            if not line:
                return None
            if line == "?":
                print(KNOWLEDGE_CMD_RULES)
                continue
            try:
                return parse_knowledge_cmd(line)
            except ValueError as e:
                print(f"⚠️ {e}")
                continue
    return None


def _run_knowledge_from_cmd(root_dir: str, cmd) -> None:
    from backend.knowledge_cmd import should_run_knowledge_cmd

    if cmd is None or not should_run_knowledge_cmd(cmd):
        return
    script = os.path.join(root_dir, "backend", "generate_demo_data.py")
    if not os.path.isfile(script):
        print("⚠️ 找不到 backend/generate_demo_data.py，略過知識庫。")
        return
    parts = [sys.executable, script, "--only", "knowledge"]
    if cmd.wipe_first:
        parts.append("--wipe-knowledge")
    parts += ["--knowledge", str(cmd.insert_n)]
    label = []
    if cmd.wipe_first:
        label.append("刪舊")
    if cmd.insert_n:
        label.append(f"寫入{cmd.insert_n}筆")
    print(f"📚 知識庫：{' + '.join(label) or '（無操作）'} …")
    r = subprocess.run(parts, cwd=root_dir)
    if r.returncode != 0:
        print("⚠️ 知識庫步驟失敗，仍繼續啟動。")
    else:
        print("   ✓ 完成")


def main() -> None:
    print("🚀 Etymon Decoder — 一鍵啟動\n")

    root_dir = os.path.abspath(os.path.dirname(__file__))
    kcmd = _resolve_start_knowledge_cmd(sys.argv)
    _run_knowledge_from_cmd(root_dir, kcmd)

    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print("❌ 找不到 uvicorn。請先執行：pip install -r requirements.txt")
        sys.exit(1)

    api_port = int(os.getenv("START_API_PORT", "8000"))

    if _port_in_use("127.0.0.1", api_port):
        print(
            f"❌ 埠 {api_port} 已被占用（常見：舊的 uvicorn 還在跑）。\n"
            f"   查詢：lsof -i :{api_port} -sTCP:LISTEN\n"
            f"   或改用：START_API_PORT=8001 python start.py\n"
        )
        sys.exit(1)

    print(f"🧠 FastAPI  http://127.0.0.1:{api_port}  （文件 /docs、健康 /health）")
    api = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "backend.api:app",
            "--reload", "--host", "127.0.0.1", "--port", str(api_port),
        ],
        cwd=root_dir,
    )

    if not _wait_api_ready(api_port):
        print("⚠️ 後端在數秒內未回應 /health，請檢查終端機錯誤訊息。")
    else:
        print("   ✓ 後端已就緒")

    web_dir = os.path.join(root_dir, "web")
    ui = None
    if os.path.isdir(web_dir) and os.path.isfile(os.path.join(web_dir, "package.json")):
        print(f"🌐 Vite 前端  http://127.0.0.1:5173  （若占用會自動換埠，請看下方輸出）")
        ui = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1"],
            cwd=web_dir,
            env={**os.environ, "START_API_PORT": str(api_port)},
            shell=sys.platform == "win32",
        )
    else:
        print("⚠️ 未找到 web/，請執行：cd web && npm install && npm run dev")

    kdn = None
    kdn_dir = os.path.join(root_dir, "kadusella")
    if os.getenv("ALSO_RUN_KADUSELLA_NEXT", "").strip().lower() in ("1", "true", "yes", "on"):
        pkg = os.path.join(kdn_dir, "package.json")
        if os.path.isfile(pkg):
            print("⚛️ kadusella Next  http://127.0.0.1:3000  （占用時 Next 會自動換埠）")
            kdn = subprocess.Popen(
                ["npm", "run", "dev", "--", "--hostname", "127.0.0.1"],
                cwd=kdn_dir,
                env={**os.environ},
                shell=sys.platform == "win32",
            )
        else:
            print("⚠️ 未找到 kadusella/package.json，略過 Next。")

    print("\n── Ctrl+C 可一併結束 ──\n")

    try:
        api.wait()
        if ui:
            ui.wait()
        if kdn:
            kdn.wait()
    except KeyboardInterrupt:
        print("\n🛑 關閉中…")
        for p in (api, ui, kdn):
            if p is not None and p.poll() is None:
                p.terminate()
        print("✅ 已結束。")


if __name__ == "__main__":
    main()
