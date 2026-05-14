#!/usr/bin/env bash
# scripts/redeploy.sh — Pull latest main and restart the loop-monitor service.
#
# Operates on the dedicated service checkout at:
#   ~/.openclaw/workspace/services/loop-monitor
#
# Bootstrap (one-time, before first run):
#   git clone https://github.com/svv2014/loop-monitor.git \
#     ~/.openclaw/workspace/services/loop-monitor
#
# Usage:
#   scripts/redeploy.sh [--checkout <path>] [--label <plist-label>]
#
# Defaults:
#   checkout: ~/.openclaw/workspace/services/loop-monitor
#   label:    com.user.loop-monitor

set -euo pipefail

CHECKOUT="${LOOP_MONITOR_SERVICE_DIR:-$HOME/.openclaw/workspace/services/loop-monitor}"
PLIST_LABEL="com.user.loop-monitor"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkout) CHECKOUT="$2"; shift 2 ;;
    --label)    PLIST_LABEL="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$CHECKOUT/.git" ]]; then
  echo "ERROR: $CHECKOUT is not a git repository." >&2
  echo "Bootstrap: git clone https://github.com/svv2014/loop-monitor.git $CHECKOUT" >&2
  exit 1
fi

echo "==> Updating checkout: $CHECKOUT"
cd "$CHECKOUT"
git fetch --quiet origin
git reset --hard origin/main

echo "==> Installing Python dependencies"
if [[ -f requirements.txt ]]; then
  pip install -r requirements.txt --quiet
fi

echo "==> Building web bundle"
cd web
npm ci --silent
npm run build
cd ..

echo "==> Restarting service: $PLIST_LABEL"
launchctl kickstart -k "gui/$(id -u)/$PLIST_LABEL"

echo "==> Done. Service is running on latest main."
