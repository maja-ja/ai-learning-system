# 正式上線給公眾使用（推薦架構）

目標：**HTTPS 網域**、**建置後的靜態前端**（非 Vite dev）、**FastAPI 僅經由 Nginx 反代**（不對外開 8000）。

---

## 上線當天（最短路径）

1. **本機**（已 clone 的專案根目錄）：
   ```bash
   bash deploy/preflight.sh
   ```
   確認無錯誤、`web/dist` 已產生。

2. **伺服器**（Ubuntu 範例，路徑請改成你的）：
   - 依下文 **§2～§6** 做一次（venv、Nginx、certbot、`/etc/etymon/api.env`、systemd）。
   - 若程式在筆電、要同步到 VPS：見 **`deploy/rsync-upload.example.sh`**（設好 `DEPLOY_TARGET` 後執行），再在伺服器上 `pip install`、`npm ci && npm run build`、`systemctl restart etymon-api`。

3. **驗收**：瀏覽器開 `https://你的網域` 與 `https://你的網域/health`。

---

## 架構一覽

```
瀏覽器 → Cloudflare（DNS + Proxy）→ 你的主機 :443 Nginx
         ├─ / 、/knowledge … → web/dist（SPA）
         └─ /api、/decode、/notes、/health … → 127.0.0.1:8000（uvicorn）
```

- **沒有固定公網 IP**：在**同一台機器**上仍先跑 Nginx + `dist` + uvicorn，再用 **Cloudflare Tunnel** 把 `etymon-decoder.com` 指到 `http://127.0.0.1:443`（或 Tunnel 直連本機 Nginx 監聽埠）。見 `POINT-ETYMON-DOMAIN.md` 方式 B。

---

## 1. 準備伺服器

- Ubuntu / Debian 類似版本即可。
- 安裝：**Python 3.11+**、**Node.js 20+**（僅建置前端需要）、**Nginx**、**certbot**（Let’s Encrypt）。

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

---

## 2. 取得程式與 Python 依賴

```bash
sudo mkdir -p /var/www/etymon-decoder && sudo chown "$USER":"$USER" /var/www/etymon-decoder
cd /var/www/etymon-decoder
git clone <你的-repo-URL> ai-learning-system
cd ai-learning-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. 建置前端（同網域：勿設 API Base）

前端與 API **同一網域**（都由 Nginx 提供）時，**不要**設定 `VITE_API_BASE_URL`，打包後會用相對路徑呼叫 `/api`、`/decode` 等。

```bash
cd web
npm ci
npm run build
cd ..
```

確認存在 **`web/dist/index.html`**。Nginx 的 `root` 須指向此 `dist` 目錄（絕對路徑）。

---

## 4. TLS 憑證

```bash
sudo certbot certonly --nginx -d etymon-decoder.com -d www.etymon-decoder.com
```

將 `deploy/nginx-etymon.example.conf` 複製到 `sites-available`，修改：

- `ssl_certificate` / `ssl_certificate_key`（certbot 路徑）
- `root` → 例如 `/var/www/etymon-decoder/ai-learning-system/web/dist`

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. 後端環境變數（正式務必檢查）

建議寫入 **`/etc/etymon/api.env`**（權限 `root:root` `chmod 600`），並由 systemd 載入（見下節）。

| 變數 | 說明 |
|------|------|
| `SUPABASE_URL` / `SUPABASE_KEY` | 雲端知識與筆記 |
| `GEMINI_API_KEY` | 講義／批量解碼等需 Gemini 的功能 |
| `ANTHROPIC_API_KEY` | 選用；單筆解碼可走 Claude（見 `AI_PROVIDER`） |
| `AI_PROVIDER` | `auto` / `gemini` / `claude` |
| `CORS_RELAX_LOCAL` | 建議 **`false`**（僅允許設定的網域與 etymon 正則） |
| `EXAM_TOKEN_SECRET` | **務必改成強隨機字串**（勿用預設） |
| `APP_PASSWORD` | 學測區密碼，請改為強密碼 |
| `LOCK_AI_FEATURES` | 若要關閉對外 `POST /decode`，設 `true` |

**不要**把 `api.env` 提交到 Git。

---

## 6. 常駐執行 uvicorn（systemd）

複製 `deploy/systemd/etymon-api.service.example` 為 `/etc/systemd/system/etymon-api.service`，修改：

- `User` / `Group`（建議專用系統使用者，且對 repo 目錄有讀取權）
- `WorkingDirectory` → clone 路徑根目錄（內含 `backend/`）
- `ExecStart` 中的 **venv 內 `uvicorn` 路徑**

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now etymon-api.service
sudo systemctl status etymon-api.service
```

本機僅監聽 **`127.0.0.1:8000`**；對外只走 Nginx。

---

## 7. 更新流程（日後改版）

```bash
cd /var/www/etymon-decoder/ai-learning-system
git pull
source .venv/bin/activate && pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..
sudo systemctl restart etymon-api.service
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. 上線驗收

- [ ] `https://etymon-decoder.com` 可開啟 SPA（重新整理子路徑如 `/knowledge` 仍正常）
- [ ] `https://etymon-decoder.com/health` 回 200
- [ ] 知識庫、解碼、講義、學測登入等你實際會用的功能各試一次
- [ ] 防火牆僅開 **80 / 443**（若無 Tunnel，則需開給 Cloudflare）；**不要**對外開 8000

---

## 9. 選用：關閉對外 API 文件

若不想公開 Swagger，需在程式內關閉 `docs_url` / `redoc_url`（目前預設開啟）；Nginx 也可拿掉 `location /docs`、`/redoc`、`/openapi.json` 區塊達到同樣效果。

---

## 相關檔案

- Nginx 範例：`nginx-etymon.example.conf`
- systemd 範例：`systemd/etymon-api.service.example`
- DNS / Tunnel / Pages：`POINT-ETYMON-DOMAIN.md`
