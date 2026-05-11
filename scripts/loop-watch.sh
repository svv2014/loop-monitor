#!/usr/bin/env bash
# loop-watch.sh — temporary observability + safe auto-unblock for the Loop pipeline.
#
# Polls loop-monitor APIs every ~2h, flags anomalies (high rework, repeated
# review cycles, stranded issues, repeated role failures), and applies a small,
# conservative set of safe label fixes (PR red CI -> needs-rework; orphaned
# issue with a full spec -> needs-po). Findings are appended as comments on a
# tracking issue.
#
# Temporary — remove after the post-stability shakedown (loop#283, #285-#289,
# bob#26) settles. To disable: `launchctl unload ~/Library/LaunchAgents/com.user.loop-watch.plist`.
#
# Usage: loop-watch.sh [--dry-run] [--tracker <issue#>]

set -euo pipefail

LOOP_MONITOR_URL="${LOOP_MONITOR_URL:-http://localhost:18792}"
LOOP_WATCH_REPO="${LOOP_WATCH_REPO:-svv2014/loop}"
LOOP_WATCH_TRACKER="${LOOP_WATCH_TRACKER:-}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --tracker) LOOP_WATCH_TRACKER="${2:?--tracker needs an issue number}"; shift 2 ;;
        -h|--help)
            sed -n '2,16p' "$0"
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

log() { printf '[loop-watch] %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# 1. Ensure tracking issue exists (create on first run if needed)
# ---------------------------------------------------------------------------
ensure_tracker() {
    if [[ -n "$LOOP_WATCH_TRACKER" ]]; then return; fi

    local existing
    existing=$(gh issue list -R "$LOOP_WATCH_REPO" \
                    --label tracker --state open --limit 50 \
                    --json number,title \
                    -q '.[] | select(.title | startswith("Loop health watch")) | .number' \
                    2>/dev/null | head -1 || true)
    if [[ -n "$existing" ]]; then
        LOOP_WATCH_TRACKER="$existing"
        log "Using existing tracker #${LOOP_WATCH_TRACKER}"
        return
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
        LOOP_WATCH_TRACKER="(dry-run)"
        log "Would create tracker issue in $LOOP_WATCH_REPO"
        return
    fi

    local url
    url=$(gh issue create -R "$LOOP_WATCH_REPO" \
            --title "Loop health watch — temporary observation log" \
            --label tracker \
            --body "Auto-created by \`scripts/loop-watch.sh\` (loop-monitor). Temporary observation log during the post-stability shakedown. Close to stop receiving updates; the watcher will recreate it on the next run unless you also disable the launchd job.")
    LOOP_WATCH_TRACKER="${url##*/}"
    log "Created tracker #${LOOP_WATCH_TRACKER}"
}

# ---------------------------------------------------------------------------
# 2. Pull pipeline state
# ---------------------------------------------------------------------------
COST_JSON=$(curl -sf --max-time 10 "${LOOP_MONITOR_URL}/api/issues/cost?limit=20" || echo '[]')
ACTIVE_JSON=$(curl -sf --max-time 10 "${LOOP_MONITOR_URL}/api/active" || echo '[]')
FEED_JSON=$(curl -sf --max-time 10 "${LOOP_MONITOR_URL}/api/feed" || echo '[]')

# ---------------------------------------------------------------------------
# 3. Analyze. Emits:
#      - markdown report on stdout (captured into $REPORT)
#      - CANDIDATE lines into $CANDIDATES_FILE (for bash to verify via gh)
# ---------------------------------------------------------------------------
CANDIDATES_FILE="/tmp/loop-watch-actions.$$"
: > "$CANDIDATES_FILE"
REPORT=$(CANDIDATES_FILE="$CANDIDATES_FILE" COST_JSON="$COST_JSON" ACTIVE_JSON="$ACTIVE_JSON" FEED_JSON="$FEED_JSON" python3 <<'PY'
import json, os, sys, collections

cost   = json.loads(os.environ.get("COST_JSON",   "[]"))
active = json.loads(os.environ.get("ACTIVE_JSON", "[]"))
feed   = json.loads(os.environ.get("FEED_JSON",   "[]"))

out, actions = [], []

# --- Anomalies from cost data --------------------------------------------
high_rework   = [r for r in cost if (r.get("rework_factor") or 0) >= 4.0]
mid_rework    = [r for r in cost if 2.0 <= (r.get("rework_factor") or 0) < 4.0]
stranded      = [r for r in cost if (r.get("stranded_seconds") or 0) > 7200]
review_hot    = [r for r in cost if (r.get("stage_runs") or {}).get("review", 0) > 3]

if high_rework:
    out.append("### Severe rework (rework_factor >= 4.0)")
    for r in high_rework:
        out.append(f"- `{r['project']}#{r['issue_number']}` — rework={r['rework_factor']} runs={r['actual_runs']} — {r.get('title','')[:80]}")
    out.append("")

if mid_rework:
    out.append("### Elevated rework (2.0 <= rework_factor < 4.0)")
    for r in mid_rework:
        out.append(f"- `{r['project']}#{r['issue_number']}` — rework={r['rework_factor']} runs={r['actual_runs']} — {r.get('title','')[:80]}")
    out.append("")

if review_hot:
    out.append("### Repeatedly reviewed (review_runs > 3)")
    for r in review_hot:
        out.append(f"- `{r['project']}#{r['issue_number']}` — review_runs={r['stage_runs']['review']}")
    out.append("")

if stranded:
    out.append("### Stranded (>2h since last event)")
    for r in stranded:
        hrs = (r['stranded_seconds'] or 0) / 3600.0
        out.append(f"- `{r['project']}#{r['issue_number']}` — stranded={hrs:.1f}h state={r.get('state')}")
    out.append("")

# --- Repeated role failures in the last hour -----------------------------
failed = collections.Counter()
for e in feed:
    et = (e.get("event_type") or "")
    age = e.get("age_seconds")
    if et.endswith("_failed") and age is not None and age <= 3600:
        role = et[:-len("_failed")]
        failed[role] += 1
hot_failures = [(r, c) for r, c in failed.items() if c > 3]
if hot_failures:
    out.append("### Repeated role failures (>3 in last hour)")
    for role, count in hot_failures:
        out.append(f"- `{role}_failed` x{count}")
    out.append("")

# --- Active pipeline summary --------------------------------------------
if active:
    out.append("### Active workers")
    for a in active:
        ref = f"#{a.get('pr_number')}" if a.get('pr_number') else (f"i#{a.get('issue_number')}" if a.get('issue_number') else "-")
        out.append(f"- {a.get('project')} · {a.get('role')} · {a.get('event_type')} · {ref}")
    out.append("")

# --- Candidates for safe auto-unblock -----------------------------------
# Collect PRs and issues currently in play from active + cost.
seen_pr, seen_issue = set(), set()
for a in active:
    if a.get("pr_number"):
        seen_pr.add((a["project"], int(a["pr_number"])))
    elif a.get("issue_number"):
        seen_issue.add((a["project"], int(a["issue_number"])))
for r in cost:
    seen_issue.add((r["project"], int(r["issue_number"])))

# Emit candidate refs for the bash side to verify via gh.
with open(os.environ["CANDIDATES_FILE"], "w") as fh:
    for proj, num in sorted(seen_pr):
        fh.write(f"CANDIDATE pr {proj} {num}\n")
    for proj, num in sorted(seen_issue):
        fh.write(f"CANDIDATE issue {proj} {num}\n")

if not out:
    out.append("_All quiet — no anomalies detected._")

print("\n".join(out))
PY
)

# ---------------------------------------------------------------------------
# 4. Verify candidates via gh; build list of safe fixes
# ---------------------------------------------------------------------------
TRIGGER_LABELS_RE='needs-po|needs-dev|needs-review|needs-qa|needs-merge|needs-rework|blocked|wip'

declare -a SAFE_FIXES=()
declare -a UNSAFE_NOTES=()

while read -r line; do
    [[ "$line" =~ ^CANDIDATE\  ]] || continue
    # shellcheck disable=SC2206
    parts=($line)
    kind="${parts[1]}"
    proj="${parts[2]}"
    num="${parts[3]}"

    case "$kind" in
        pr)
            pr_json=$(gh pr view "$num" -R "$proj" --json labels,state 2>/dev/null || echo "")
            [[ -z "$pr_json" ]] && continue
            state=$(printf '%s' "$pr_json" | python3 -c "import sys,json;print(json.load(sys.stdin).get('state',''))" 2>/dev/null || echo "")
            [[ "$state" != "OPEN" ]] && continue
            labels=$(printf '%s' "$pr_json" | python3 -c "import sys,json;print(' '.join(l['name'] for l in json.load(sys.stdin).get('labels',[])))" 2>/dev/null || echo "")
            ci=$(gh pr checks "$num" -R "$proj" --json state 2>/dev/null | python3 -c "
import sys,json
try: chk=json.load(sys.stdin)
except Exception: chk=[]
print('failed' if any(c.get('state','').upper() in ('FAILURE','ERROR') for c in chk) else 'ok')
" 2>/dev/null || echo "unknown")
            if [[ "$ci" == "failed" ]] && ! echo " $labels " | grep -q " needs-rework "; then
                if echo " $labels " | grep -qE " ($TRIGGER_LABELS_RE) "; then
                    UNSAFE_NOTES+=("- \`${proj}#${num}\` (PR) has red CI but already carries a trigger label (\`${labels}\`) — manual review")
                else
                    SAFE_FIXES+=("pr ${proj} ${num} needs-rework")
                fi
            fi
            ;;
        issue)
            issue_json=$(gh issue view "$num" -R "$proj" --json labels,body,state 2>/dev/null || echo "")
            [[ -z "$issue_json" ]] && continue
            state=$(printf '%s' "$issue_json" | python3 -c "import sys,json;print(json.load(sys.stdin).get('state',''))" 2>/dev/null || echo "")
            [[ "$state" != "OPEN" ]] && continue
            labels=$(printf '%s' "$issue_json" | python3 -c "import sys,json;print(' '.join(l['name'] for l in json.load(sys.stdin).get('labels',[])))" 2>/dev/null || echo "")
            body_len=$(printf '%s' "$issue_json" | python3 -c "import sys,json;print(len((json.load(sys.stdin).get('body') or '').strip()))" 2>/dev/null || echo "0")
            has_spec=$(printf '%s' "$issue_json" | python3 -c "
import sys,json
b=(json.load(sys.stdin).get('body') or '').lower()
print('1' if ('## acceptance' in b or '## spec' in b or '## requirements' in b) else '0')
" 2>/dev/null || echo "0")
            if [[ "$has_spec" == "1" || "$body_len" -gt 500 ]]; then
                if ! echo " $labels " | grep -qE " ($TRIGGER_LABELS_RE) "; then
                    SAFE_FIXES+=("issue ${proj} ${num} needs-po")
                fi
            fi
            ;;
    esac
done < "$CANDIDATES_FILE"
rm -f "$CANDIDATES_FILE"

# ---------------------------------------------------------------------------
# 5. Apply safe fixes (or print under --dry-run)
# ---------------------------------------------------------------------------
APPLIED_NOTES=""
for fix in "${SAFE_FIXES[@]:-}"; do
    [[ -z "$fix" ]] && continue
    # shellcheck disable=SC2206
    f=($fix)
    kind="${f[0]}"; proj="${f[1]}"; num="${f[2]}"; label="${f[3]}"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        APPLIED_NOTES+="- [dry-run] would add \`${label}\` to ${kind} \`${proj}#${num}\`"$'\n'
        log "[dry-run] would label ${kind} ${proj}#${num} -> ${label}"
    else
        if [[ "$kind" == "pr" ]]; then
            gh pr edit "$num" -R "$proj" --add-label "$label" >/dev/null 2>&1 \
                && APPLIED_NOTES+="- applied \`${label}\` to PR \`${proj}#${num}\`"$'\n' \
                || APPLIED_NOTES+="- failed to apply \`${label}\` to PR \`${proj}#${num}\`"$'\n'
        else
            gh issue edit "$num" -R "$proj" --add-label "$label" >/dev/null 2>&1 \
                && APPLIED_NOTES+="- applied \`${label}\` to issue \`${proj}#${num}\`"$'\n' \
                || APPLIED_NOTES+="- failed to apply \`${label}\` to issue \`${proj}#${num}\`"$'\n'
        fi
    fi
done

# ---------------------------------------------------------------------------
# 6. Post comment on tracking issue
# ---------------------------------------------------------------------------
ensure_tracker

UNSAFE_BLOCK=""
if [[ ${#UNSAFE_NOTES[@]} -gt 0 ]]; then
    UNSAFE_BLOCK=$'\n### Unsafe — needs manual review\n'"$(printf '%s\n' "${UNSAFE_NOTES[@]}")"
fi

APPLIED_BLOCK=""
if [[ -n "$APPLIED_NOTES" ]]; then
    APPLIED_BLOCK=$'\n### Auto-actions\n'"${APPLIED_NOTES}"
fi

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMENT_BODY="## loop-watch report — ${NOW}

${REPORT}
${APPLIED_BLOCK}${UNSAFE_BLOCK}
_dry_run=${DRY_RUN} · monitor=${LOOP_MONITOR_URL}_"

if [[ "$DRY_RUN" -eq 1 || "$LOOP_WATCH_TRACKER" == "(dry-run)" ]]; then
    log "[dry-run] would post on ${LOOP_WATCH_REPO}#${LOOP_WATCH_TRACKER}:"
    printf '%s\n' "$COMMENT_BODY"
else
    gh issue comment "$LOOP_WATCH_TRACKER" -R "$LOOP_WATCH_REPO" --body "$COMMENT_BODY" >/dev/null
    log "Posted report on ${LOOP_WATCH_REPO}#${LOOP_WATCH_TRACKER}"
fi
