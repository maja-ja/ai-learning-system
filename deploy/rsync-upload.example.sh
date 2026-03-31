#!/usr/bin/env bash
# 複製為 rsync-upload.sh（勿提交含真實主機的版本），或直接用環境變數執行本檔。
#
# 用法：
#   export DEPLOY_TARGET=ubuntu@YOUR_IP:/var/www/etymon-decoder/ai-learning-system
#   bash deploy/rsync-upload.example.sh
#
# 同步後請 SSH 到伺服器依 docs/deploy/PRODUCTION-RUNBOOK.md 執行 pip / npm run build / systemctl restart。

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${DEPLOY_TARGET:?請設定 DEPLOY_TARGET，例如 user@host:/path/to/ai-learning-system}"

rsync -avz \
  --exclude '.git' \
  --exclude 'web/node_modules' \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude 'streamlit_app/__pycache__' \
  --exclude '**/*.pyc' \
  --exclude 'backend/local_knowledge.db' \
  --exclude '.env' \
  --exclude 'web/.env' \
  --exclude 'web/.env.*' \
  "$ROOT/" "$TARGET/"

echo "rsync 完成。伺服器上：cd $TARGET && source .venv/bin/activate && pip install -r requirements.txt && cd web && npm ci && npm run build && sudo systemctl restart etymon-api"
