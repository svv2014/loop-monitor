#!/usr/bin/env bash
# redeploy.sh — pull latest main into the dedicated service checkout and restart.
#
# One-time bootstrap (not scripted — do this once, then use this script):
#   git clone https://github.com/svv2014/loop-monitor.git \
#       ~/.openclaw/workspace/services/loop-monitor
#
# Usage:  scripts/redeploy.sh [--service-dir <path>]
#
# Exits non-zero on any failed step (set -e).

set -euo pipefail

SERVICE_DIR="${LOOP_MONITOR_SERVICE_DIR:-${HOME}/.openclaw/workspace/services/loop-monitor}"
PLIST_LABEL="com.user.loop-monitor"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service-dir) SERVICE_DIR="${2:?--service-dir needs a path}"; shift 2 ;;
        -h|--help)
            sed -n '2,10p' "$0"
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

log() { printf '[redeploy] %s\n' "$*"; }

if [[ ! -d "${SERVICE_DIR}/.git" ]]; then
    echo "ERROR: ${SERVICE_DIR} is not a git repository." >&2
    echo "Bootstrap with: git clone https://github.com/svv2014/loop-monitor.git ${SERVICE_DIR}" >&2
    exit 1
fi

cd "${SERVICE_DIR}"

log "Fetching latest main..."
git fetch origin

log "Resetting to origin/main..."
git reset --hard origin/main

if [[ -f requirements.txt ]]; then
    log "Installing Python dependencies..."
    pip install -r requirements.txt --quiet
fi

log "Building frontend..."
cd web
npm ci --silent
npm run build
cd ..

log "Restarting service (${PLIST_LABEL})..."
launchctl kickstart -k "gui/$(id -u)/${PLIST_LABEL}"

log "Done. Service restarted from $(git rev-parse --short HEAD)."
