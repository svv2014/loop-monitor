#!/usr/bin/env bash
# install-loop-watch.sh — render com.user.loop-watch.plist with the absolute
# path to this checkout and install it into ~/Library/LaunchAgents/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ $# -ge 1 ]]; then
    MONITOR_ROOT="$(cd "$1" && pwd)"
else
    MONITOR_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
TEMPLATE="$SCRIPT_DIR/com.user.loop-watch.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST="$DEST_DIR/com.user.loop-watch.plist"

mkdir -p "$DEST_DIR"

# sed -i differs between macOS and GNU; write to a temp file and move.
tmp="$(mktemp)"
sed "s|{{LOOP_MONITOR_ROOT}}|$MONITOR_ROOT|g" "$TEMPLATE" > "$tmp"
mv "$tmp" "$DEST"

launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"

echo "Installed $DEST"
