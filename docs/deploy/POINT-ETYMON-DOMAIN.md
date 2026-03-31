# 將 etymon-decoder.com 指向本專案

網域須已在 **Cloudflare** 託管（DNS 伺服器為 Cloudflare）。依你的主機型態擇一即可。

---

## 方式 A：有固定 IP 的 VPS（最常見）

### 1. DNS（Cloudflare → DNS → 記錄）

| 類型 | 名稱 | 內容 | Proxy |
|------|------|------|-------|
| A | `@` | 你的伺服器 **公網 IP** | 已代理（橘雲） |
| A 或 CNAME | `www` | 同 IP，或 CNAME 到 `@` | 已代理 |
| A（選用） | `api` | 同一台機器若 API 要獨立子網域 | 已代理 |

SSL/TLS 模式：**Full** 或 **Full (strict)**（本機有合法憑證時用 strict）。

### 2. 伺服器上：建前端 + 跑後端

```bash
cd /path/to/ai-learning-system
pip install -r requirements.txt
cd web && npm ci && npm run build
# 若前端與 API 同網域，勿設 VITE_API_BASE_URL（用相對路徑）
```

### 3. Nginx（同網域：靜態 + 反代 API）

複製並修改 `deploy/nginx-etymon.example.conf` 中的 `server_name`、憑證路徑、`root` 指向你機器上的 `web/dist` 絕對路徑。

```bash
sudo certbot certonly --nginx -d etymon-decoder.com -d www.etymon-decoder.com
sudo nginx -t && sudo systemctl reload nginx
```

後端需監聽本機（僅 Nginx 反代，不對外開 8000）：

```bash
uvicorn backend.api:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips='*'
```

（可用 systemd 常駐。）

### 4. 後端環境變數（伺服器）

- `SUPABASE_URL` / `SUPABASE_KEY`、`GEMINI_API_KEY` 等照常設定。
- 正式環境建議：`CORS_RELAX_LOCAL=false`，並確認 `CORS_EXTRA_ORIGINS` 已含你實際前端網址（若與 `etymon-decoder.com` 同源則通常不必再加）。

---

## 方式 B：沒有固定公網 IP（本機 / 內網）— Cloudflare Tunnel

1. 安裝並登入：[cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
2. `cloudflared tunnel login` → 選你的網域。
3. `cloudflared tunnel create etymon-decoder`
4. **Zero Trust** → **Networks** → **Tunnels** → 該隧道 → **Public Hostname**：
   - **Subdomain**：`@` 或留空（視介面）對應根網域 `etymon-decoder.com`
   - **Domain**：`etymon-decoder.com`
   - **Service**：建議指到你本機 **Nginx**（例如 `http://127.0.0.1:80`），由 Nginx 同時提供 `dist` 與 `/api` 反代（與方式 A 相同架構，只是對外改由 Tunnel 進來）。
5. 保持 **`cloudflared tunnel run …` 常駐**（關機／睡眠會出現 **Error 1033**）。

參考：`deploy/cloudflare-tunnel.example.yml`。

### 臨時示範：Tunnel 直連本機 Vite（5173 / 5174）

`127.0.0.1` 只有在你電腦上有效，**無法**用 DNS 直接指到它；必須在本機跑 `cloudflared`，把 `etymon-decoder.com` 轉進本機 HTTP。

1. **Public Hostname** 的 **Service** 設為：`http://127.0.0.1:5174`（若 Vite 實際在 5173 就改埠號）。
2. 本機先啟動前端（例如 `python start.py` 或 `cd web && npm run dev`）。
3. **HMR（熱更新）** 經 Tunnel 時，在 `web` 目錄啟動前加上環境變數：
   ```bash
   VITE_DEV_TUNNEL=1 npm run dev
   ```
   （`web/vite.config.ts` 已設定 `allowedHosts` 與上述條件式 `hmr`。）

僅供開發／示範：**不要**長期把對外網域指到 Vite dev；正式環境請用 `npm run build` + Nginx（或 Pages），見上文方式 A / C。

---

## 方式 C：前端 Cloudflare Pages + API 子網域

1. **Pages** 專案：Build 指令 `cd web && npm run build`，輸出目錄 `web/dist`。
2. Pages **環境變數**設：`VITE_API_BASE_URL=https://api.etymon-decoder.com`（再建置一次）。
3. **自訂網域**：`etymon-decoder.com` 綁到該 Pages 專案。
4. **API**：`api.etymon-decoder.com` 用 Tunnel 或 VPS 指到 `uvicorn :8000`，且後端 CORS 已包含 Pages 網域（本專案已含 `etymon-decoder.com` 與子網域規則）。

---

## 檢查清單

- [ ] 瀏覽器網址為 `https://etymon-decoder.com`（**點**不是逗號）
- [ ] 前端能開、API `https://etymon-decoder.com/health` 或 `https://api.../health` 回 200
- [ ] 同網域時：**不要**在 production 把 `VITE_API_BASE_URL` 指到自己又指錯路徑；分網域時必設正確 API 根網址
- [ ] Tunnel 使用者：**cloudflared 必須一直在跑**

專案內 CORS 與 `VITE_API_BASE_URL` 說明見根目錄 **README.md**。
