#!/usr/bin/env bash
# scripts/redeploy.sh — update the service checkout to latest main and restart.
#
# Run this whenever the dashboard shows a "Update available" banner.
# Idempotent: safe to run repeatedly.
#
# Prerequisites (one-time setup — see README.md "Service checkout"):
#   git clone https://github.com/svv2014/loop-monitor.git \
#       ~/.openclaw/workspace/services/loop-monitor

set -euo pipefail

SERVICE_DIR="${LOOP_MONITOR_SERVICE_DIR:-$HOME/.openclaw/workspace/services/loop-monitor}"
PLIST_LABEL="com.user.loop-monitor"

if [[ ! -d "$SERVICE_DIR/.git" ]]; then
  echo "ERROR: service checkout not found at $SERVICE_DIR" >&2
  echo "Bootstrap it first:" >&2
  echo "  git clone https://github.com/svv2014/loop-monitor.git $SERVICE_DIR" >&2
  exit 1
fi

cd "$SERVICE_DIR"

echo "==> Fetching latest main..."
git fetch --quiet origin main
git reset --hard origin/main

echo "==> Installing Python dependencies..."
if [[ -f requirements.txt ]]; then
  pip install -r requirements.txt --quiet
fi

echo "==> Building web bundle..."
cd web
npm ci --silent
npm run build
cd ..

echo "==> Restarting service..."
launchctl kickstart -k "gui/$(id -u)/$PLIST_LABEL"

echo "==> Done. Service is running on latest main."
