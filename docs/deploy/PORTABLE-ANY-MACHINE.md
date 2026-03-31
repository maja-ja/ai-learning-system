# 帶著這個資料夾，在任意機器上對外跑網站

目標：**同一個 repo 目錄**，換電腦也能用；**不必裝 Nginx**，Cloudflare Tunnel **只指一個埠**即可（前端 + API 同源）。

---

## 原理

1. 執行 `cd web && npm ci && npm run build` 產生 `web/dist`。
2. 設 **`SERVE_WEB_DIST=1`** 啟動 FastAPI 時，會同時：
   - 提供 **`/api`、`/decode`、`/notes`…**（與原本相同）
   - 提供 **SPA 靜態檔**（`/assets/*`、其餘前端路由回 `index.html`）
3. 瀏覽器只連 **一個 origin**（例如 `https://etymon-decoder.com`），**不要**設定 `VITE_API_BASE_URL`。

---

## 在新機器上一次準備

```bash
cd /path/to/ai-learning-system
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 選填：把環境變數寫入 .env，後端會讀（依你專案慣例）
```

---

## 啟動（單埠）

```bash
source .venv/bin/activate
python serve_portable.py
```

- 若尚未建置，會自動執行 `npm ci` + `npm run build`（需已安裝 Node.js）。
- 已建置過、只想重啟後端：`SKIP_WEB_BUILD=1 python serve_portable.py`
- 換埠：`START_API_PORT=8001 python serve_portable.py`

本機驗證：<http://127.0.0.1:8000/> 與 <http://127.0.0.1:8000/health>

---

## Cloudflare Tunnel（建議）

1. 在專案根目錄建立 **`.cloudflared/`**，放入 Cloudflare 給你的 **`*.json` 憑證**（勿提交 Git；已列在 `.gitignore`）。
2. 複製 `deploy/config.portable.example.yml` 為 **`config.yml`**（根目錄，已 gitignore），把 `tunnel:`、`credentials-file` 改成你的值。  
   `credentials-file` 可用**相對於執行 `cloudflared` 時的當前目錄**的路徑，例如：`.cloudflared/<uuid>.json`
3. **Ingress 只留一條主機名**指到本機服務即可，例如：
   ```yaml
   - hostname: etymon-decoder.com
     service: http://127.0.0.1:8000
   ```
   若以前有 **`api.etymon-decoder.com` 指到 8000**、主站指 Streamlit，請改成：**主站 → 8000**（或刪除多餘 hostname，避免混用舊設定）。
4. 在**專案根目錄**執行：
   ```bash
   cloudflared tunnel --config config.yml run
   ```

---

## 與「正式 VPS + Nginx」的差異

| 項目 | 單埠 `serve_portable.py` | Nginx + `dist` |
|------|---------------------------|----------------|
| 安裝 | Python + Node（建置時） | 另裝 Nginx、憑證 |
| 適合 | 筆電示範、快速上線、Tunnel | 長期高流量、慣用反代 |

大流量或要細緻快取時，仍建議 **`PRODUCTION-RUNBOOK.md`**（同目錄）的 Nginx 架構。
