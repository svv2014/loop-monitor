#!/usr/bin/env bash
# Redeploy loop-monitor from the dedicated service checkout.
# Idempotent — safe to run multiple times.
# Usage: scripts/redeploy.sh
set -euo pipefail

SERVICE_DIR="${LOOP_MONITOR_SERVICE_DIR:-$HOME/.openclaw/workspace/services/loop-monitor}"
PLIST_LABEL="com.user.loop-monitor"

if [[ ! -d "$SERVICE_DIR/.git" ]]; then
  echo "ERROR: $SERVICE_DIR is not a git repository." >&2
  echo "Bootstrap: git clone https://github.com/svv2014/loop-monitor.git $SERVICE_DIR" >&2
  exit 1
fi

cd "$SERVICE_DIR"

echo "==> Fetching origin/main ..."
git fetch origin
git reset --hard origin/main

if [[ -f requirements.txt ]]; then
  echo "==> Installing Python dependencies ..."
  pip install -r requirements.txt --quiet
fi

echo "==> Building web frontend ..."
cd web
npm ci --silent
npm run build
cd ..

echo "==> Restarting $PLIST_LABEL ..."
launchctl kickstart -k "gui/$(id -u)/$PLIST_LABEL"

echo "==> Done. Running $(git rev-parse --short HEAD)."
