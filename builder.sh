#!/usr/bin/env bash
# builder.sh — dev-handler.sh with bounty reporting.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/bounty.sh
source "$SCRIPT_DIR/lib/bounty.sh"

SLUG="${Loop_SLUG:-}"
REF="${Loop_ISSUE_NUMBER:-}"

bounty_report "builder" "$SLUG" "$REF" "working"

_handler="$SCRIPT_DIR/dev-handler.sh"
[ -x "$_handler" ] || _handler="${Loop_ROOT:?Loop_ROOT is required}/scripts/dev-handler.sh"

if "$_handler" "$@"; then
    bounty_report "builder" "$SLUG" "$REF" "done"
else
    _rc=$?
    bounty_report "builder" "$SLUG" "$REF" "failed"
    exit "$_rc"
fi
