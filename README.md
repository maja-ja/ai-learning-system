# AI 教育工作站

主介面為 **Vite + React**（`web/`），後端 **FastAPI**（`backend/`），資料儲存於本機 **SQLite**（`backend/local.db`）。

## 架構概覽

```
ai-learning-system/
├── web/          # Vite + React 主學習介面（5 頁）
├── backend/      # FastAPI API 伺服器 + SQLite 資料庫
├── kadusella/    # Next.js + Supabase 管理控制台（選用）
├── 知識/         # Markdown 知識語料庫
├── docs/         # 部署文件
└── deploy/       # 部署設定範本
```

## 一鍵啟動（推薦）

需已安裝 Python 依賴與 Node.js，且曾執行過 `cd web && npm install`。

```bash
cd /path/to/ai-learning-system
pip install -r requirements.txt
python start.py
```

macOS / Linux 也可：`./start.sh`

- 後端：<http://127.0.0.1:8000>（含 `--reload` 熱重載）
- 前端：<http://127.0.0.1:5173>（埠被占用時 Vite 會自動換埠）
- 啟動前會檢查 **8000 是否被占用**；可改用 `START_API_PORT=8001 python start.py`

## 手動分開啟動

```bash
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
# 另開終端機
cd web && npm run dev
```

## 建置前端

```bash
cd web && npm run build
```

產出於 `web/dist/`，請將 `/api`、`/decode`、`/notes` 等反向代理到 FastAPI。

### 任意機器單埠上線（無 Nginx）

複製專案到任何電腦後：`pip install -r requirements.txt`，再執行 **`python serve_portable.py`**（會自動建置 `web/dist` 並以 **同一埠** 提供 SPA + API）。Cloudflare Tunnel 只需指到 `http://127.0.0.1:8000`，**勿**設 `VITE_API_BASE_URL`。詳見 **`docs/deploy/PORTABLE-ANY-MACHINE.md`**。

## 前端頁面

| 路徑 | 功能 |
|------|------|
| `/knowledge` | 知識庫瀏覽 · 今日隨機啟發 · 朗讀 · 一鍵生成講義 |
| `/roots` | 高中英文字根 · 首頁概覽 / 圖鑑 / 小測驗 |
| `/lab` | 解碼實驗室 · 批量 AI 解碼 · Aha hook 閉環 |
| `/exam` | 學測資料庫 · 本地 Markdown 樹 · 全文搜尋 · 編輯 |
| `/handout` | 講義排版 · 模板 / AI 生成 / 圖片旋轉 / 歷史紀錄 |

## 資料與 AI 行為

| 項目 | 說明 |
|------|------|
| `backend/local.db` | 本機 SQLite 主資料庫（知識卡、筆記、Aha 事件等） |
| `GET /api/knowledge` | 讀取本機 SQLite 知識庫；回傳 `meta.source: "local"` |
| `POST /decode` | 預設**開放**；AI 解碼後寫入本機 SQLite |
| `GET/POST /notes` | 本機 SQLite 筆記 CRUD |
| `GEMINI_API_KEY` | 使用 Gemini 時必填 |
| `ANTHROPIC_API_KEY` | 使用 Claude 時必填 |
| `AI_PROVIDER` | `gemini` / `claude` / `auto`（預設 **auto**：有 Anthropic 金鑰則走 Claude，否則 Gemini） |
| `CLAUDE_MODEL` | 例如 `claude-3-5-sonnet-20241022`（可自訂新版號） |
| `GEMINI_MODEL` | 預設 `gemini-2.5-flash` |
| `AI_PROVIDER_CHEAP` / `AI_PROVIDER_QUALITY` | 任務分級路由（便宜任務 vs 高品質任務） |
| `GEMINI_MODEL_CHEAP` / `GEMINI_MODEL_QUALITY` | Gemini 分級模型 |
| `CLAUDE_MODEL_CHEAP` / `CLAUDE_MODEL_QUALITY` | Claude 分級模型 |

## 環境變數（摘要）

| 變數 | 說明 |
|------|------|
| `LOCK_AI_FEATURES` | 設為 `true` 時關閉 `POST /decode`（預設開放） |
| `CORS_RELAX_LOCAL` | 預設 `true`，允許 `localhost` / `127.0.0.1` 任意埠跨域 |
| `CORS_EXTRA_ORIGINS` | 逗號分隔的額外 Origin |
| `CORS_INCLUDE_ETYMON_REGEX` | 預設 `true`，允許 `*.etymon-decoder.com` |
| `VITE_API_BASE_URL` | 前端建置時寫入，指向公開的 FastAPI 根網址（同域時留空） |
| `APP_PASSWORD` | 學測區密碼（預設 `abcd`，正式環境請修改） |
| `EXAM_TOKEN_SECRET` | 學測區 token 簽章金鑰（正式環境請修改） |
| `MAINTENANCE_TOKEN` | 啟用維護端點的 Bearer token（未設即關閉） |

## API 端點摘要

- `GET /api/knowledge` — 知識列表
- `GET /api/knowledge/export` — 下載 `knowledge_markdown.zip`
- `GET /api/roots` — 高中字根 JSON
- `POST /decode` — 單筆 AI 解碼並儲存（Claude／Gemini）
- `POST /api/decode/batch` — 批量解碼（**Gemini**，跨領域視角）
- `POST /api/decode/suggest-topics` — 隨機主題靈感
- `POST /api/learner/context` — 設定學習者年齡層與地區背景
- `GET /api/aha/hooks/recommend` — 依 age_band/region_code 推薦 Aha hook
- `POST /api/aha/events` — 單筆 Aha 事件寫入
- `POST /api/aha/events/batch` — 批次 Aha 事件寫入
- `GET /api/admin/db/status` — 維運檢查資料庫狀態（需 `MAINTENANCE_TOKEN`）
- `POST /api/admin/aha/events/backfill-variant` — 回填 `hook_variant_id`（需 `MAINTENANCE_TOKEN`）
- `POST /api/handout/generate` — 講義 Markdown（Gemini，可附圖）
- `POST /api/handout/preview-html` — A4 可列印 HTML
- `GET /notes`、`POST /notes`、`PUT /notes/{id}`、`DELETE /notes/{id}` — 筆記 CRUD
- `POST /api/exam/login` 與 `GET /api/exam/*` — 學測本地 Markdown 區

## Cloudflare × etymon-decoder.com（橋接）

**正式上線逐步操作**：見 **`docs/deploy/PRODUCTION-RUNBOOK.md`**。  
**把網域指到本專案**：見 **`docs/deploy/POINT-ETYMON-DOMAIN.md`**；Nginx 範例：`deploy/nginx-etymon.example.conf`。

### 後端 CORS

已預設允許：

- `https://etymon-decoder.com`、`www`、`api` 子網域
- 正則：任意 `*.etymon-decoder.com`
- 本機 `localhost` / `127.0.0.1` 任意埠（可關：`CORS_RELAX_LOCAL=false`）

### 前端呼叫 API（不同網域時必設）

在 **`web/.env.production`** 或 Cloudflare Pages 環境變數設定：

```bash
VITE_API_BASE_URL=https://api.etymon-decoder.com
```

若同一網域由 Nginx 反代，可**不設**此變數。

## kadusella（管理控制台，選用）

`kadusella/` 是獨立的 **Next.js + Supabase + Clerk** 子專案，提供知識圖譜管理與 Aha hook 設定介面。

啟動：

```bash
cd kadusella && npm install && npm run dev
```

或在根目錄：

```bash
ALSO_RUN_KADUSELLA_NEXT=true python start.py
```

> kadusella 使用自己的 `.env.local` 管理 Supabase/Clerk 金鑰，與主 web/ 前端獨立。
