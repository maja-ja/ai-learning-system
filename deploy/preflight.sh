#!/usr/bin/env bash
# 上線前在本機執行：確認 web 可正式建置（產出 web/dist）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web"
npm ci
npm run build
echo "preflight OK: $ROOT/web/dist"
