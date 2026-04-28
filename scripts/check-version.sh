#!/usr/bin/env bash
# check-version.sh — detect when loop core is behind the latest GitHub release and notify.
# Invoke via a separate launchd StartInterval plist or cron entry, NOT from run.sh.
# Example cron: 0 * * * * /path/to/scripts/check-version.sh
# Example launchd key: <key>StartInterval</key><integer>3600</integer>
set -euo pipefail

LOOP_ROOT="${LOOP_ROOT:-/Users/vadim/.openclaw/workspace/projects/loop}"
LOOP_ENV="$LOOP_ROOT/loop.env"
[[ -f "$LOOP_ENV" ]] && source "$LOOP_ENV"

installed=$(cat "$LOOP_ROOT/VERSION" 2>/dev/null | sed 's/^v//')
[[ -z "$installed" ]] && exit 0

latest=$(gh release view --repo svv2014/loop --json tagName --jq .tagName 2>/dev/null | sed 's/^v//')
[[ -z "$latest" ]] && exit 0

[[ "$installed" == "$latest" ]] && exit 0

STATE_FILE="/tmp/loop-version-last-notified"
now=$(date +%s)
if [[ -f "$STATE_FILE" ]]; then
    last=$(cat "$STATE_FILE")
    (( now - last < 3600 )) && exit 0
fi

msg="Loop update available: v${installed} → v${latest}. Run update.sh to apply."
"${LOOP_NOTIFY:-echo}" "$msg"
echo "$now" > "$STATE_FILE"
