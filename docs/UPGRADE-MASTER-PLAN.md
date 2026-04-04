# Etymon Decoder — 全面升級總規劃

> 版本：2026-04-04 初稿
> 範圍：基礎設施、後端、前端、實驗室、部署、DX、Raspberry Pi 5 移植

---

## 目錄

1. [現狀總覽](#1-現狀總覽)
2. [Raspberry Pi 5 (4 GB) 可行性分析](#2-raspberry-pi-5-4-gb-可行性分析)
3. [升級第零階段 — 安全護網](#3-升級第零階段--安全護網)
4. [升級第一階段 — 基礎體質](#4-升級第一階段--基礎體質)
5. [升級第二階段 — 產品體驗](#5-升級第二階段--產品體驗)
6. [升級第三階段 — 規模與可觀測](#6-升級第三階段--規模與可觀測)
7. [升級第四階段 — 進階功能](#7-升級第四階段--進階功能)
8. [RPi 5 專屬部署方案](#8-rpi-5-專屬部署方案)
9. [時程與優先矩陣](#9-時程與優先矩陣)
10. [附錄：檔案異動清單](#10-附錄檔案異動清單)

---

## 1. 現狀總覽

### 1.1 架構圖

```
使用者瀏覽器
    │
    ▼
Cloudflare（DNS / Proxy / Tunnel）
    │
    ▼
┌──────────────────────────────────────────────────┐
│ 主機（VPS / 筆電 / RPi）                           │
│                                                    │
│  Nginx（正式）或 serve_portable.py（單埠）          │
│    ├─ /assets/*          → web/dist（靜態 SPA）    │
│    ├─ /api/*、/decode     → FastAPI :8000          │
│    └─ 其餘前端路由        → index.html             │
│                                                    │
│  FastAPI (uvicorn)                                 │
│    ├─ backend/api.py        路由層                  │
│    ├─ backend/database.py   SQLite + Supabase 雙寫 │
│    ├─ backend/ai_decode.py  Gemini / Claude 解碼   │
│    ├─ backend/decoder_batch.py  批量解碼            │
│    ├─ backend/handout_gen.py    講義生成            │
│    └─ backend/member_auth.py    會員驗證            │
│                                                    │
│  SQLite: backend/local.db                          │
└──────────────────────────────────────────────────┘

    ┌────────────── 雲端服務 ──────────────┐
    │ Supabase (Postgres + Edge Functions)  │
    │ Clerk (會員驗證)                       │
    │ Gemini / Claude API (AI 推理)         │
    │ kadusella (Next.js 計費站)             │
    └───────────────────────────────────────┘
```

### 1.2 技術棧摘要

| 層級 | 技術 | 版本 |
|------|------|------|
| 前端 | Vite + React + TypeScript + Tailwind | Vite 6, React 18, TS 5.6 |
| 路由 | react-router-dom | v7 |
| 認證 | Clerk | @clerk/clerk-react ^5.61 |
| 後端 | FastAPI + Uvicorn | fastapi (unpinned) |
| 資料庫 | SQLite (主) + Supabase Postgres (雲) | — |
| AI | Google Gemini + Anthropic Claude | google-genai, anthropic |
| 計費 | kadusella (Next.js 16 + Supabase) | Line Pay / PayPal |
| 部署 | 手動 rsync / Cloudflare Tunnel | — |

### 1.3 已知問題摘要

| 類別 | 問題數 | 最嚴重項目 |
|------|--------|-----------|
| 測試 | 0 檔案 | 零測試覆蓋 |
| CI/CD | 0 pipeline | 純手動部署 |
| 容器 | 0 Docker | 架構文件提到但不存在 |
| 後端 | database.py 1524 行 | 巨石模組，難以維護 |
| 前端 | index.css 用 !important 覆寫 | 全域樣式脆弱 |
| 依賴 | requirements.txt 無版本鎖 | pandas 零引用但仍列入 |
| 安全 | 弱預設密碼 | APP_PASSWORD="abcd" |
| 架構 | 雙軌 AI 路徑 | FastAPI vs Supabase Edge 需手動同步 prompts |

---

## 2. Raspberry Pi 5 (4 GB) 可行性分析

### 2.1 結論：完全可行

RPi 5 4GB 可以穩定運行本專案的**生產環境**。關鍵原因：

1. **AI 推理在雲端** — Gemini / Claude 呼叫走 HTTP API，Pi 只負責請求轉發
2. **SQLite 原生支援** — 不需額外 DB 伺服器，記憶體開銷極低
3. **已有 `serve_portable.py`** — 單埠部署模式，設計理念就是「帶著資料夾換機器跑」
4. **Cloudflare Tunnel 已設定** — 不需公網 IP、不需 Nginx、不需 certbot

### 2.2 記憶體預算

| 程序 | 預估 RAM | 備註 |
|------|----------|------|
| Raspberry Pi OS Lite (64-bit) | ~180 MB | 無桌面環境 |
| Python 3.11 + FastAPI/Uvicorn (1 worker) | ~120–200 MB | 含載入模組 |
| cloudflared | ~30–50 MB | Tunnel daemon |
| SQLite (in-process) | ~10–30 MB | 看資料量 |
| 系統緩衝 / 檔案快取 | ~200 MB | 留給 kernel |
| **執行期合計** | **~540–660 MB** | |
| **可用餘量** | **~3.3–3.5 GB** | 充裕 |

### 2.3 需要注意的事項

| 項目 | 風險 | 解法 |
|------|------|------|
| `npm run build` 記憶體尖峰 | Vite + TypeScript 編譯可達 1.5 GB | 在開發機 build 好 `web/dist/`，rsync 到 Pi；或加 2 GB swap |
| `pip install` 編譯 | Pillow 需編譯 C 擴展 | 用系統套件 `apt install python3-pillow`，或在 Pi 上加 swap |
| pandas（150 MB+）| 安裝慢且佔空間 | **直接移除** — 整個專案零引用 |
| SD 卡 I/O | SQLite WAL 寫入壽命 | 用 USB SSD（強烈建議）或 tmpfs + 定期 sync |
| ARM64 套件相容性 | google-genai, anthropic 皆有 ARM wheel | 已驗證 PyPI 有 aarch64 版 |
| 併發能力 | 單 worker 處理 ~5–10 QPS | 足夠個人 / 小團隊使用 |
| kadusella (Next.js) | 額外吃 300–500 MB | **不在 Pi 上跑** — 部署到 Vercel 或 Cloudflare Pages |

### 2.4 推薦硬體配置

```
Raspberry Pi 5 (4 GB)
├─ 儲存：USB 3.0 SSD（128 GB+）掛載為根檔案系統
├─ 散熱：官方主動散熱器或 Pi 5 散熱殼
├─ 電源：官方 5V/5A USB-C 電源
├─ 網路：有線乙太網（穩定性優於 WiFi）
└─ 作業系統：Raspberry Pi OS Lite 64-bit (Bookworm)
```

### 2.5 與 VPS 的比較

| 面向 | RPi 5 4GB | 雲端 VPS (2C/2G) |
|------|-----------|-------------------|
| 月成本 | 電費 ~NT$30（5W 均功耗） | NT$150–500/月 |
| 延遲 | Cloudflare Tunnel 增加 ~20ms | 機房直連，延遲低 |
| 可靠性 | 依家用網路穩定度 | 99.9% SLA |
| 維護 | 自己管硬體 + OS 更新 | 供應商管硬體 |
| 擴展 | 受限 4 GB RAM | 可隨時升規格 |
| 適合場景 | 個人學習站、Demo、低流量 | 正式公開服務 |

---

## 3. 升級第零階段 — 安全護網

> 目標：在動任何大改之前，先建立安全網，確保不會把東西搞壞。
> 預估：1–2 天

### 3.1 依賴鎖定

**問題**：`requirements.txt` 只有 7 行，無版本號；缺少 `pillow`（`handout_gen.py` 的 `from PIL import Image`）；`pandas` 零引用。

**動作**：

```
# 目標 requirements.txt
fastapi>=0.115,<1.0
uvicorn[standard]>=0.34,<1.0
pydantic>=2.10,<3.0
google-genai>=1.0,<2.0
anthropic>=0.42,<1.0
pillow>=11.0,<12.0
markdown>=3.7,<4.0
# pandas 已移除（零引用）
```

- 可選進階：加入 `uv` 或 `pip-tools` 產出 `requirements.lock`，鎖完整依賴樹

### 3.2 啟動安全檢查

**問題**：`APP_PASSWORD="abcd"`、`EXAM_TOKEN_SECRET="dev-exam-secret-change-me"` 在生產環境若未覆蓋，形同裸奔。

**動作**：在 `api.py` 啟動時檢查，若為預設值且非本機開發，印出警告或拒絕啟動：

```python
if not os.getenv("ALLOW_DEV_DEFAULTS") and APP_PASSWORD == "abcd":
    raise RuntimeError("生產環境請設定 APP_PASSWORD 環境變數")
```

### 3.3 基礎 pytest 骨架

**目標**：建立 `tests/` 目錄，先寫 5 個最關鍵的測試，讓後續重構有保險。

```
tests/
├── conftest.py              # FastAPI TestClient fixture
├── test_health.py           # GET /health 回 200
├── test_knowledge_api.py    # GET /api/knowledge 回正確結構
├── test_decode_schema.py    # KnowledgeCard Pydantic 驗證
├── test_model_router.py     # resolve_provider / resolve_gemini_model 邏輯
└── test_batch_body.py       # BatchDecodeBody 驗證（max 30、delay 範圍）
```

### 3.4 Git pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: tsc
        name: TypeScript type check
        entry: npx tsc --noEmit
        language: system
        files: \.tsx?$
        pass_filenames: false
```

---

## 4. 升級第一階段 — 基礎體質

> 目標：拆解巨石、統一資料層、加入快取與 code splitting。
> 預估：3–5 天

### 4.1 database.py 拆檔

將 1524 行的 `database.py` 拆為清晰的模組：

```
backend/
├── db/
│   ├── __init__.py           # re-export 常用函式，向後相容
│   ├── connection.py         # SQLite 連線管理、Lock、schema migration
│   ├── knowledge.py          # knowledge_list, knowledge_upsert, knowledge_delete_all
│   ├── notes.py              # notes_create, notes_list, notes_update, notes_delete
│   ├── member_storage.py     # member_storage_create, member_storage_list, member_storage_delete
│   ├── learner.py            # learner_context_upsert, learner_context_get
│   ├── aha.py                # aha_hooks_*, aha_event_*
│   ├── tracking.py           # click_events_insert_batch, click_recent_actions, click_markov_predict
│   └── supabase_sync.py      # knowledge_sync_to_supabase, _supabase_request
├── database.py               # 過渡期：from db import * （向後相容，標記 deprecated）
```

**原則**：先拆，不改邏輯；現有 import 不壞。加 `# DEPRECATED: import from backend.db instead` 到舊 `database.py`。

### 4.2 SQLite / Supabase schema 對齊

**問題**：`click_events` 在 Supabase 有 `tenant_id`, `profile_id`, `metadata` 欄位，SQLite 版缺少。`learner_contexts` 也有差異。

**動作**：

1. 將 SQLite schema 擴展為 Supabase 的超集
2. 寫 migration script：`backend/db/migrations/001_align_schemas.py`
3. 在 `connection.py` 啟動時自動執行未跑過的 migration（用 `schema_version` 表追蹤）

### 4.3 前端加入 React Query

**收益**：自動快取、背景更新、loading/error 狀態統一管理、減少手動 `useState` + `useEffect` 模式。

```
npm install @tanstack/react-query
```

改動影響的頁面：

| 頁面 | 目前 | 改後 |
|------|------|------|
| Knowledge | `useEffect` + `fetchKnowledge` | `useQuery({ queryKey: ['knowledge'], queryFn: fetchKnowledge })` |
| Roots | `useEffect` + `fetchRoots` | `useQuery({ queryKey: ['roots'], queryFn: fetchRoots })` |
| Exam | `useEffect` + `fetchExamTree` | `useQuery` + `useMutation` for save |
| Lab (batch) | 手動 state | `useMutation` with `onSuccess` invalidation |
| Account | `fetchMemberStorage` | `useQuery` + optimistic delete |

### 4.4 前端 Code Splitting

```tsx
// App.tsx
const Lab = lazy(() => import("./pages/Lab"));
const Exam = lazy(() => import("./pages/Exam"));
const Handout = lazy(() => import("./pages/Handout"));
const Account = lazy(() => import("./pages/Account"));

// 在 Layout 裡包 <Suspense fallback={<Skeleton />}>
```

預期效果：首頁 bundle 減少 ~30–40%，Knowledge 頁載入更快。

### 4.5 清理死碼

- 刪除 `web/src/pages/Dashboard.tsx`（無路由引用）
- 從 `requirements.txt` 移除 `pandas`
- 整理 `streamlit_app/` — 移入 `archive/` 或刪除

### 4.6 統一 AI model 版本

**問題**：FastAPI `model_router.py` 預設 `gemini-2.5-flash`；Supabase Edge `_shared/gemini.ts` 預設 `gemini-2.0-flash`。

**動作**：

1. 兩邊統一為 `gemini-2.5-flash`（或統一由環境變數讀取）
2. 在 `prompts_prod.py` 加上版本標記 header，Edge 端對齊
3. 長期：選定一個 canonical source，另一邊自動生成

---

## 5. 升級第二階段 — 產品體驗

> 目標：實驗室大改版、知識地圖動態化、全站 UX 提升。
> 預估：5–8 天

### 5.1 批量解碼 — 串流進度

**現狀**：前端送出 30 筆，乾等 1–2 分鐘，無任何回饋。

**改法**：

後端：

```python
@app.post("/api/decode/batch-stream")
async def batch_stream(body: BatchDecodeBody, member=Depends(...)):
    async def generate():
        for i, word in enumerate(words):
            yield sse_event({"i": i, "total": len(words), "word": word, "status": "processing"})
            try:
                row = await asyncio.to_thread(decode_interdisciplinary, word, ...)
                yield sse_event({"i": i, "word": word, "status": "done", "row": row})
            except Exception as e:
                yield sse_event({"i": i, "word": word, "status": "error", "detail": str(e)})
    return StreamingResponse(generate(), media_type="text/event-stream")
```

前端：

```tsx
const source = new EventSource("/api/decode/batch-stream?...");
source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  setProgress(prev => [...prev, data]);
};
```

UI 效果：每筆出現即時狀態卡片（解碼中 → 完成 / 跳過 / 錯誤），頂部進度條。支援「中途取消」。

### 5.2 批量解碼 — 結果預覽再存入

**現狀**：AI 產出直接寫入，品質無法把關。

**改法**：

1. SSE 完成後進入「Review Mode」
2. 每張知識卡以可展開卡片呈現
3. 點擊可編輯各欄位（definition, breakdown, memory_hook 等）
4. 有「全部確認」和「逐張確認 / 丟棄 / 重新生成」按鈕
5. 確認後才呼叫新的 persist API

### 5.3 知識地圖 — 從靜態到動態

**現狀**：`knowledgeMap.ts` 硬編碼 3 棵固定樹，與實際知識庫無關。

**改法**：

```
GET /api/knowledge/graph
→ 從 knowledge 表讀出所有 row
→ 以 category 建群組節點
→ 以 synonym_nuance 提取的概念名建關聯邊
→ 回傳 { nodes: [...], edges: [...] }
```

前端選擇：

| 方案 | 優點 | 缺點 |
|------|------|------|
| `@xyflow/react` (React Flow) | React 生態、拖拉、縮放、Mini-map | 套件較大 (~60 KB gzip) |
| `d3-force` + 自製 SVG | 輕量、完全控制 | 開發成本高 |
| **建議**：先用 d3-force 做基礎版 | 與現有 SVG 知識地圖風格一致 | 後期可換 React Flow |

功能：

- 節點大小 = 該概念關聯數量
- 顏色 = category 分群
- 已解碼的概念填色，未解碼的空心
- 點擊節點 → 彈出知識卡預覽
- 搜尋、按領域過濾、縮放平移

### 5.4 領域選擇器改版

**現狀**：30+ 按鈕平鋪，UX 差。

**改法**：

```tsx
<CategoryPicker
  categories={CATEGORIES}          // 5 大類、每類 4-7 子項
  primary={primary}
  aux={aux}
  recentCombinations={recentCombos} // localStorage 記住最近用過的組合
  onSave={(name, combo) => ...}     // 命名儲存常用組合
/>
```

- Accordion 分組（語言與邏輯 / 科學與技術 / …）
- 「最近使用」和「推薦組合」置頂
- 搜尋過濾
- 組合可命名儲存

### 5.5 全域 Error Boundary

```tsx
// components/ErrorBoundary.tsx
class ErrorBoundary extends Component<Props, State> {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} onReset={...} />;
    }
    return this.props.children;
  }
}
```

套用到 `App.tsx` 最外層 + 每個 `<Route>` 的 `errorElement`。

### 5.6 CSS 清理

移除 `index.css` 中的 `[class*="bg-indigo-"]` 等子字串選擇器（~60 行），改用 Tailwind `@layer base` + CSS 變數管理主題色：

```css
@layer base {
  :root {
    --color-surface: #ffffff;
    --color-text: #111111;
    --color-border: #000000;
    --color-accent: #000000;
  }
}
```

---

## 6. 升級第三階段 — 規模與可觀測

> 目標：CI/CD、Docker、監控、自動備份。
> 預估：3–5 天

### 6.1 GitHub Actions CI

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run ruff check backend/
      - run: uv run pytest tests/ -v

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
        working-directory: web
      - run: npx tsc --noEmit
        working-directory: web
      - run: npm run build
        working-directory: web
```

### 6.2 Docker 化

```dockerfile
# Dockerfile
FROM python:3.11-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM node:20-slim AS frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ .
RUN npm run build

FROM base AS runtime
COPY --from=frontend /web/dist /app/web/dist
COPY backend/ /app/backend/
COPY start.py serve_portable.py ./
ENV SERVE_WEB_DIST=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.api:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./backend/local.db:/app/backend/local.db
      - ./知識:/app/知識:ro
    restart: unless-stopped
```

RPi 5 亦可用此 Docker 映像（ARM64 base image 自動匹配）。

### 6.3 結構化 Logging

將全專案的 `print(f"Error: {e}")` 替換為 Python `logging`：

```python
import logging
logger = logging.getLogger("etymon")

# 統一 JSON 格式 handler（方便未來接 Loki / CloudWatch）
```

### 6.4 錯誤追蹤

```
pip install sentry-sdk[fastapi]
```

```python
import sentry_sdk
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN", ""), traces_sample_rate=0.1)
```

### 6.5 自動備份 (cron / systemd timer)

```ini
# /etc/systemd/system/etymon-backup.timer
[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

搭配 `backend/backup_local_db.py --keep 30`。RPi 上同樣適用。

### 6.6 健康監控

- Cloudflare Health Check 或 UptimeRobot 打 `https://etymon-decoder.com/health`
- 異常時透過 Slack / Telegram / LINE Notify 告警

---

## 7. 升級第四階段 — 進階功能

> 目標：深度產品功能，提升留存率。
> 預估：5–10 天（可拆開分批做）

### 7.1 智慧排程佇列

- 前端維護「主題待辦清單」，存 localStorage + `member_storage`
- 支援拖拉排序、從 CSV / 剪貼簿批次匯入
- 「繼續上次未完成」：記住 batch 中斷位置
- 預設主題包（如「大一物理 30 核心概念」）一鍵載入

### 7.2 學習統計儀表板

- 新增 Lab → 「歷史」tab
- 從 `member_storage` (feature=decode_batch) 拉取紀錄
- 圖表：每日 / 每週解碼量、領域分布圓餅圖
- 學習足跡時間線——點進去回顧任何一次 batch 結果

### 7.3 講義雙語 / 多語

- `handout_gen.py` prompt 擴充語言參數
- 前端選擇：繁中 / 英文 / 雙語並陳
- 英文學術講義可用於國際讀者或語言學習

### 7.4 知識卡 Anki 匯出

- `GET /api/knowledge/export-anki`
- 產出 `.apkg` 格式（使用 `genanki` 套件）
- 讓使用者帶走知識卡到 Anki 複習

### 7.5 PWA 離線模式

```json
// web/public/manifest.json
{
  "name": "Etymon Decoder",
  "short_name": "Etymon",
  "start_url": "/knowledge",
  "display": "standalone",
  "theme_color": "#000000"
}
```

配合 Service Worker 快取知識庫頁面，離線可瀏覽已解碼的內容。

---

## 8. RPi 5 專屬部署方案

### 8.1 OS 安裝

```bash
# Raspberry Pi Imager → Raspberry Pi OS Lite (64-bit, Bookworm)
# 設定：
#   - hostname: etymon-pi
#   - SSH: 啟用
#   - Wi-Fi: 選用（建議有線）
#   - 使用者：etymon / <強密碼>
```

### 8.2 SSD 掛載（強烈建議）

```bash
# 假設 USB SSD 為 /dev/sda1
sudo mkdir -p /mnt/ssd
sudo mount /dev/sda1 /mnt/ssd
# 加入 /etc/fstab 持久掛載
echo '/dev/sda1 /mnt/ssd ext4 defaults,noatime 0 2' | sudo tee -a /etc/fstab

# 專案放在 SSD
sudo mkdir -p /mnt/ssd/etymon && sudo chown etymon:etymon /mnt/ssd/etymon
```

### 8.3 系統套件

```bash
sudo apt update && sudo apt install -y \
  python3 python3-venv python3-pip \
  python3-pillow \
  git curl
```

Node.js（僅在 Pi 上 build 時需要，建議在開發機 build）：

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 8.4 Swap 設定

```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### 8.5 部署步驟

```bash
cd /mnt/ssd/etymon
git clone <repo-url> ai-learning-system
cd ai-learning-system

# Python 環境
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 前端（方案 A：在 Pi 上 build）
cd web && npm ci && npm run build && cd ..

# 前端（方案 B：從開發機 rsync dist/）
# 在開發機：rsync -avz web/dist/ etymon@etymon-pi.local:/mnt/ssd/etymon/ai-learning-system/web/dist/

# 環境變數
cp deploy/config.portable.example.yml config.yml
# 編輯 config.yml — 填入 Tunnel UUID

cat > .env << 'EOF'
GEMINI_API_KEY=<your-key>
ANTHROPIC_API_KEY=<your-key>
APP_PASSWORD=<strong-password>
EXAM_TOKEN_SECRET=<random-64-char>
MEMBERSHIP_TOKEN_SECRET=<random-64-char>
EOF

# 測試啟動
SKIP_WEB_BUILD=1 python serve_portable.py
# 瀏覽器開 http://etymon-pi.local:8000/health
```

### 8.6 systemd 服務（開機自啟）

```ini
# /etc/systemd/system/etymon-api.service
[Unit]
Description=Etymon Decoder API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=etymon
WorkingDirectory=/mnt/ssd/etymon/ai-learning-system
EnvironmentFile=/mnt/ssd/etymon/ai-learning-system/.env
Environment=SERVE_WEB_DIST=1 SKIP_WEB_BUILD=1
ExecStart=/mnt/ssd/etymon/ai-learning-system/.venv/bin/python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=*
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/etymon-tunnel.service
[Unit]
Description=Cloudflare Tunnel for Etymon
After=network-online.target etymon-api.service
Wants=network-online.target

[Service]
Type=simple
User=etymon
WorkingDirectory=/mnt/ssd/etymon/ai-learning-system
ExecStart=/usr/local/bin/cloudflared tunnel --config config.yml run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now etymon-api etymon-tunnel
```

### 8.7 自動備份 + 監控

```ini
# /etc/systemd/system/etymon-backup.timer
[Unit]
Description=Daily SQLite backup

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/etymon-backup.service
[Unit]
Description=Run Etymon backup

[Service]
Type=oneshot
User=etymon
WorkingDirectory=/mnt/ssd/etymon/ai-learning-system
ExecStart=/mnt/ssd/etymon/ai-learning-system/.venv/bin/python backend/backup_local_db.py --keep 30
```

### 8.8 RPi 效能調優

```bash
# 減少不必要的服務
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon

# 固定 CPU 頻率（避免降頻）
echo 'arm_freq=2400' | sudo tee -a /boot/firmware/config.txt
echo 'over_voltage=4' | sudo tee -a /boot/firmware/config.txt

# 限制日誌佔用
sudo journalctl --vacuum-size=100M
```

---

## 9. 時程與優先矩陣

### 9.1 四階段甘特圖

```
Week 1          Week 2          Week 3          Week 4          Week 5+
├── Phase 0 ────┤
│ 依賴鎖定       │
│ 安全檢查       │
│ pytest 骨架    │
│ pre-commit     │
│               ├── Phase 1 ────────────────┤
│               │ database.py 拆檔            │
│               │ React Query                 │
│               │ Code Splitting              │
│               │ 死碼清理                     │
│               │ AI model 統一               │
│               │                            ├── Phase 2 ─────────────────┤
│               │                            │ SSE 串流進度                 │
│               │                            │ 結果預覽再存入               │
│               │                            │ 動態知識地圖                 │
│               │                            │ 領域選擇器                   │
│               │                            │ Error Boundary              │
│               │                            │ CSS 清理                    │
│               │                            │                            ├── Phase 3+
│               │                            │                            │ CI/CD
│               │                            │                            │ Docker
│               │                            │                            │ Logging
│               │                            │                            │ RPi 部署
│               │                            │                            │ 進階功能
```

### 9.2 完整優先排序

| 優先級 | 項目 | 投入 | 風險 | 收益 |
|--------|------|------|------|------|
| **P0** | requirements.txt 版本鎖 + 移除 pandas + 補 pillow | 30 min | 低 | 防部署爆炸 |
| **P0** | 啟動安全檢查（弱密碼阻擋） | 30 min | 低 | 安全底線 |
| **P0** | pytest 骨架（5 個核心測試） | 2 hr | 低 | 重構保險 |
| **P0** | pre-commit + ruff | 30 min | 低 | DX 品質門檻 |
| **P1** | database.py 拆檔 | 3 hr | 中 | 後續所有改動基礎 |
| **P1** | React Query | 2 hr | 低 | 全站體驗立即改善 |
| **P1** | Code Splitting + 刪 Dashboard.tsx | 1 hr | 低 | 載入效能 |
| **P1** | AI model 版本統一 | 1 hr | 低 | 消除隱形 bug |
| **P1** | 批量解碼 SSE 串流 | 4 hr | 中 | Lab 體驗大升級 |
| **P1** | 結果預覽再存入 | 3 hr | 中 | 品質把關 |
| **P2** | 動態知識地圖 | 5 hr | 中 | 產品差異化核心 |
| **P2** | 領域選擇器改版 | 2 hr | 低 | UX 明顯改善 |
| **P2** | GitHub Actions CI | 2 hr | 低 | 防壞 code 上線 |
| **P2** | Error Boundary | 1 hr | 低 | 穩定性 |
| **P2** | CSS 清理 | 2 hr | 中 | 可維護性 |
| **P2** | 結構化 logging | 2 hr | 低 | 線上問題可追蹤 |
| **P3** | Docker 化 | 3 hr | 低 | 部署一致性 |
| **P3** | RPi 5 部署 | 2 hr | 低 | 低成本生產環境 |
| **P3** | Sentry | 1 hr | 低 | 錯誤可追蹤 |
| **P3** | 自動備份 timer | 30 min | 低 | 資料安全 |
| **P3** | Schema 對齊 migration | 2 hr | 中 | 資料一致性 |
| **P4** | 智慧排程佇列 | 4 hr | 中 | 進階用戶留存 |
| **P4** | 學習統計儀表板 | 5 hr | 中 | 留存率 |
| **P4** | Anki 匯出 | 3 hr | 低 | 差異化功能 |
| **P4** | PWA 離線模式 | 3 hr | 中 | 行動端體驗 |
| **P4** | 多語講義 | 2 hr | 低 | 受眾擴大 |
| **P4** | Streamlit 歸檔 | 30 min | 低 | 減少困惑 |

### 9.3 RPi 部署的前置條件

RPi 5 部署只依賴 Phase 0 完成即可開始：

```
Phase 0（依賴鎖定 + 安全檢查）
    ↓
RPi 5 部署（§8 全流程）
    ↓
之後所有 Phase 的改動可在 Pi 上 git pull + restart 即生效
```

---

## 10. 附錄：檔案異動清單

### 新增檔案

| 檔案 | 階段 | 說明 |
|------|------|------|
| `tests/conftest.py` | P0 | pytest fixtures |
| `tests/test_health.py` | P0 | 健康檢查測試 |
| `tests/test_knowledge_api.py` | P0 | 知識 API 測試 |
| `tests/test_decode_schema.py` | P0 | schema 驗證測試 |
| `tests/test_model_router.py` | P0 | model 路由測試 |
| `tests/test_batch_body.py` | P0 | 批量請求體測試 |
| `.pre-commit-config.yaml` | P0 | pre-commit hooks |
| `ruff.toml` | P0 | Python linter 設定 |
| `backend/db/__init__.py` | P1 | 新 DB 模組入口 |
| `backend/db/connection.py` | P1 | 連線管理 |
| `backend/db/knowledge.py` | P1 | 知識庫 CRUD |
| `backend/db/notes.py` | P1 | 筆記 CRUD |
| `backend/db/member_storage.py` | P1 | 會員存儲 |
| `backend/db/learner.py` | P1 | 學習者上下文 |
| `backend/db/aha.py` | P1 | Aha hook 相關 |
| `backend/db/tracking.py` | P1 | 點擊追蹤 |
| `backend/db/supabase_sync.py` | P1 | Supabase 同步 |
| `web/src/components/CategoryPicker.tsx` | P2 | 領域選擇器元件 |
| `web/src/components/BatchProgress.tsx` | P2 | 串流進度元件 |
| `web/src/components/ResultReview.tsx` | P2 | 結果預覽元件 |
| `web/src/components/ErrorBoundary.tsx` | P2 | 錯誤邊界 |
| `Dockerfile` | P3 | 容器映像 |
| `docker-compose.yml` | P3 | 容器編排 |
| `.github/workflows/ci.yml` | P3 | CI pipeline |

### 修改檔案

| 檔案 | 階段 | 說明 |
|------|------|------|
| `requirements.txt` | P0 | 版本鎖定、移除 pandas、加 pillow |
| `backend/api.py` | P0/P1/P2 | 安全檢查、SSE endpoint |
| `backend/database.py` | P1 | 改為 re-export wrapper |
| `web/package.json` | P1 | 加 @tanstack/react-query |
| `web/src/App.tsx` | P1/P2 | lazy imports、error boundary |
| `web/src/pages/Lab.tsx` | P2 | SSE + review + 領域選擇器 |
| `web/src/components/KnowledgeMapView.tsx` | P2 | 動態知識圖譜 |
| `web/src/index.css` | P2 | 清理 !important 覆寫 |

### 刪除檔案

| 檔案 | 階段 | 說明 |
|------|------|------|
| `web/src/pages/Dashboard.tsx` | P1 | 死碼 |
| `streamlit_app/` (整個目錄) | P4 | 已被 web/ 取代 |

---

*本文件為活文件，隨各階段實施更新。*
