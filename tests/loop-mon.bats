#!/usr/bin/env bats
# tests/loop-mon.bats — bats tests for bin/loop-mon
# Requires: bats-core, jq, curl (mocked via PATH shim)

SCRIPT="${BATS_TEST_DIRNAME}/../bin/loop-mon"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
HEALTH_JSON='{"status":"ok","monitor_version":"0.1.1","supported_bounty_api":"1.x","core_version_counts":{}}'
BOARD_JSON='[{"project":"loop","role":"dev","model":"sonnet","total_points":185,"verdict_count":10},{"project":"loop","role":"review","model":"opus","total_points":120,"verdict_count":8}]'
FEED_JSON='[{"id":1,"project":"loop","role":"dev","model":"sonnet","event_type":"merge_done","issue_number":4,"pr_number":4,"detail":"+13 bounty","payload":null,"created_at":"2026-04-28T07:22:00+00:00","age_seconds":60},{"id":2,"project":"loop","role":"dev","model":"sonnet","event_type":"qa_pass","issue_number":4,"pr_number":4,"detail":null,"payload":null,"created_at":"2026-04-28T07:21:00+00:00","age_seconds":120}]'
STATUS_JSON='[{"project":"loop","role":"dev","model":"sonnet","event_type":"merge_done","issue_number":4,"pr_number":4,"detail":null,"payload":null,"created_at":"2026-04-28T07:22:00+00:00"},{"project":"loop","role":"review","model":"opus","event_type":"review_done","issue_number":4,"pr_number":4,"detail":null,"payload":null,"created_at":"2026-04-28T07:20:00+00:00"}]'

setup() {
    # Create a temp dir for the curl shim
    SHIM_DIR="$(mktemp -d)"
    export SHIM_DIR

    # Write a curl shim that returns fixture data based on the URL path
    cat > "${SHIM_DIR}/curl" <<'EOF'
#!/usr/bin/env bash
# Minimal curl shim — returns fixture JSON based on last path segment
url=""
for arg in "$@"; do
    case "$arg" in
        http://*|https://*) url="$arg" ;;
    esac
done
case "$url" in
    */api/health)  printf '%s' "${HEALTH_JSON}" ;;
    */api/board)   printf '%s' "${BOARD_JSON}" ;;
    */api/feed)    printf '%s' "${FEED_JSON}" ;;
    */api/status)  printf '%s' "${STATUS_JSON}" ;;
    *)             exit 1 ;;
esac
EOF
    chmod +x "${SHIM_DIR}/curl"

    # Export fixture vars so the shim can read them
    export HEALTH_JSON BOARD_JSON FEED_JSON STATUS_JSON
    export PATH="${SHIM_DIR}:${PATH}"
}

teardown() {
    rm -rf "${SHIM_DIR}"
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@test "--version prints loop-mon v<version>" {
    run "${SCRIPT}" --version
    [ "${status}" -eq 0 ]
    [[ "${output}" == "loop-mon v"* ]]
}

@test "--help exits 0" {
    run "${SCRIPT}" --help
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"Usage:"* ]]
}

@test "-h exits 0" {
    run "${SCRIPT}" -h
    [ "${status}" -eq 0 ]
}

@test "one-shot snapshot contains LOOP MONITOR header" {
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"LOOP MONITOR"* ]]
}

@test "one-shot snapshot contains LEADERBOARD section" {
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"LEADERBOARD"* ]]
}

@test "one-shot snapshot contains LIVE FEED section" {
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"LIVE FEED"* ]]
}

@test "one-shot snapshot contains JUDGE VERDICTS section" {
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"JUDGE VERDICTS"* ]]
}

@test "one-shot snapshot shows model name from board" {
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"sonnet"* ]]
}

@test "one-shot snapshot shows event type from feed" {
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"merge_done"* ]]
}

@test "--board-only shows leaderboard without feed" {
    run "${SCRIPT}" --no-color --board-only
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"LEADERBOARD"* ]]
    [[ "${output}" == *"sonnet"* ]]
    [[ "${output}" != *"LIVE FEED"* ]]
}

@test "--feed-only shows feed without leaderboard header" {
    run "${SCRIPT}" --no-color --feed-only
    [ "${status}" -eq 0 ]
    [[ "${output}" == *"LIVE FEED"* ]]
    [[ "${output}" != *"LEADERBOARD"* ]]
}

@test "--json emits valid JSON with all keys" {
    run "${SCRIPT}" --json
    [ "${status}" -eq 0 ]
    echo "${output}" | jq -e '.health and .board and .feed and .status' >/dev/null
}

@test "--json health.status is ok" {
    run "${SCRIPT}" --json
    [ "${status}" -eq 0 ]
    local val
    val=$(echo "${output}" | jq -r '.health.status')
    [ "${val}" = "ok" ]
}

@test "--no-color output has no ANSI escape codes" {
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 0 ]
    # cat -v would show ^[ for ESC; check raw bytes instead
    [[ "${output}" != *$'\033'* ]]
}

@test "unknown option exits non-zero" {
    run "${SCRIPT}" --unknown-flag-xyz
    [ "${status}" -ne 0 ]
}

@test "server down exits 1 in one-shot mode" {
    # Override curl to always fail
    cat > "${SHIM_DIR}/curl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
    run "${SCRIPT}" --no-color
    [ "${status}" -eq 1 ]
}
