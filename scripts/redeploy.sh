#!/usr/bin/env bash
# redeploy.sh — pull latest main to the dedicated service checkout and restart the service.
#
# One-time bootstrap (run once, not by this script):
#   git clone https://github.com/svv2014/loop-monitor.git \
#       ~/.openclaw/workspace/services/loop-monitor
#
# Then to redeploy:
#   bash scripts/redeploy.sh
#
# Idempotent — safe to run repeatedly.

set -euo pipefail

SERVICE_DIR="${HOME}/.openclaw/workspace/services/loop-monitor"
PLIST_LABEL="com.user.loop-watch"

if [[ ! -d "$SERVICE_DIR/.git" ]]; then
    echo "ERROR: Service checkout not found at $SERVICE_DIR" >&2
    echo "Bootstrap it first:" >&2
    echo "  git clone https://github.com/svv2014/loop-monitor.git $SERVICE_DIR" >&2
    exit 1
fi

cd "$SERVICE_DIR"

echo "[redeploy] Fetching latest main..."
git fetch origin
git reset --hard origin/main

if [[ -f requirements.txt ]]; then
    echo "[redeploy] Installing Python dependencies..."
    pip install -r requirements.txt --quiet
fi

echo "[redeploy] Building frontend..."
cd web
npm ci --silent
npm run build

cd "$SERVICE_DIR"

echo "[redeploy] Restarting service (label: ${PLIST_LABEL})..."
launchctl kickstart -k "gui/$(id -u)/${PLIST_LABEL}"

echo "[redeploy] Done."
