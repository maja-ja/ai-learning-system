import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 與根目錄 start.py 的 START_API_PORT 對齊（一鍵啟動會注入）
const API_TARGET = `http://127.0.0.1:${process.env.START_API_PORT || "8000"}`;

// 經 Cloudflare Tunnel 用 https://etymon-decoder.com 開本機 dev 時設為 1，並搭配下方 hmr
const devTunnel = process.env.VITE_DEV_TUNNEL === "1";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    // 允許以自訂網域 Host 標頭連進 dev server（Tunnel）
    allowedHosts: [
      "etymon-decoder.com",
      "www.etymon-decoder.com",
      ".etymon-decoder.com",
    ],
    ...(devTunnel
      ? {
          hmr: {
            host: "etymon-decoder.com",
            protocol: "wss",
            clientPort: 443,
          },
        }
      : {}),
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/decode": { target: API_TARGET, changeOrigin: true },
      "/notes": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
});
