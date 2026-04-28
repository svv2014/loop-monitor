#!/usr/bin/env bash
# loop-monitor/run.sh — launch the Loop Monitor server.
# Called by the LaunchAgent plist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

exec python3 -m uvicorn server.app:app --host 127.0.0.1 --port 18792
