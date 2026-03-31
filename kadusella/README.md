# Kadusella

本目錄為 **整合進 ai-learning-system 的 Next.js 切片**：控制台 + Supabase（pgvector、Edge Functions）。與倉庫共用的 **Markdown 題庫在倉庫根目錄 `知識/`**（由根目錄 `streamlit_app/` 讀寫）；**FastAPI 與 Streamlit 請用倉庫根目錄** 的 `backend/`、`streamlit_app/`、`start.py`。

## 目錄一覽（`kadusella/` 內）

| 路徑 | 說明 |
|------|------|
| `app/`, `public/` | Next.js 16（App Router） |
| `supabase/` | `migrations/`、`functions/`（decode、RAG、handout 等） |
| `scripts/` | CSV → etymon JSON、遠端 Supabase 操作等 |
| `docs/` | 架構與講義優化筆記 |
| `archive/` | 非正式產線的備份頁面（例如舊 HTML） |

**倉庫根（與本目錄同層）**：`知識/`、`web/`（Vite）、`backend/`、`streamlit_app/`、`assets/`、`start.py`。

## 常用指令

```bash
# 本目錄：Next
cd kadusella && npm install && npm run dev

# 倉庫根：Vite + API（可選 Streamlit、本 Next）
# ALSO_RUN_STREAMLIT=true ALSO_RUN_KADUSELLA_NEXT=true python3 start.py
python3 start.py

# 倉庫根：由現有知識庫建置數學知識圖譜
python3 kadusella/scripts/build_math_knowledge_graph.py --out docs/samples/math_knowledge_graph_v1.json
```

環境變數：複製 `.env.example`（若專案有）或依 `lib/supabase`、`scripts/supabase-remote.mjs` 說明設定 `.env.local`。

## 原 create-next-app 文件

部署與 Next.js 功能說明見 [Next.js 官方文件](https://nextjs.org/docs)。
