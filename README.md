# loop-monitor — Companion dashboard for Loop

> Live agent status, bounty leaderboard, AI judge verdicts, PR scorecards.
> The visibility layer for the [Loop](https://github.com/svv2014/loop) pipeline.

> **Renamed from bounty-monitor** — `loop-monitor` is the direct successor to [`svv2014/bounty-monitor`](https://github.com/svv2014/bounty-monitor) (now archived). The API, event schema, and port (18792) are identical — no migration needed.

## What it shows

```
┌─────────────────────────────────────────────────────────────┐
│                      LOOP MONITOR                            │
│                http://localhost:18792                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐      │
│  │ Planner  │  │ Builder  │  │ Reviewer │  │ Tester │      │
│  │ 🟢 idle  │  │ 🔵 busy  │  │ 🟢 idle  │  │ 🟡 qa  │      │
│  │ 52 pts   │  │ 185 pts  │  │ 120 pts  │  │ 74 pts │      │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘      │
│                                                              │
│  LIVE FEED                           BOUNTY BOARD            │
│  • 🔵 Builder working #35           1. sonnet   185 pts    │
│  • ✅ Reviewer approved #301         2. opus     120 pts    │
│  • 🏆 Merged #42 → +13 bounty       3. haiku     12 pts    │
│                                                              │
│  JUDGE VERDICT (PR #42):                                     │
│  "Clean merge, solid spec, no rework. Full bounty."          │
└─────────────────────────────────────────────────────────────┘
```

## What it does

- **Live status** — every Loop handler sends events as it works
  (`dev_start`, `review_done`, `qa_pass`, `merge_done`, etc.). The
  dashboard renders them in real time.
- **Bounty leaderboard** — points awarded per role per merged PR.
  Different agents/models accumulate scores. Helps you see which
  configurations work best.
- **AI judge** — runs after every merge, reads the PR timeline, posts
  a scorecard comment with role-level points + a one-sentence verdict.
- **History tab** — full run table, timeline view, stats cards.
- **Work queue** — cross-project pipeline backlog with priority ordering.

## Install

```bash
git clone https://github.com/svv2014/loop-monitor.git
cd loop-monitor
pip install -r requirements.txt
./run.sh
```

`run.sh` is the server entrypoint — it starts the uvicorn process on port 18792.

Open http://127.0.0.1:18792.

## Wire it to Loop

In your Loop core's `loop.env`:

```bash
LOOP_BOUNTY_URL=http://127.0.0.1:18792
```

That's it. Loop's handlers send fire-and-forget bounty events to the
monitor. If the monitor is down, the pipeline is unaffected.

## API

### `POST /api/report` — bounty event ingestion (v1.0)

Versioned payload per the bounty event API contract. Loop core sends
this on every pipeline state change.

```json
{
  "api": "1.0",
  "core_version": "0.1.0",
  "event": "dev_done",
  "role": "dev",
  "agent": "claude",
  "model": "sonnet",
  "project": "ppl",
  "issue_num": 42,
  "pr_num": 100,
  "detail": "attempt 1/3",
  "timestamp": "2026-04-27T04:00:00Z"
}
```

- Accepts `api: "1.x"` — gracefully ignores unknown fields
- Rejects future major versions (`api: "2.x"`) with HTTP 426
- Missing `api` field treated as `"1.0"` legacy

### `GET /api/health` — monitor status

```json
{
  "status": "ok",
  "monitor_version": "0.1.1",
  "supported_bounty_api": "1.x",
  "core_version_counts": {"0.1.0": 42}
}
```

`core_version_counts` — map of Loop core version → event count, built from ingested events.

## Data Retention

`bounty.db` grows at ~600 events/day. Run `scripts/prune.py` nightly to keep it bounded.

```bash
python scripts/prune.py --db bounty.db
python scripts/prune.py --db bounty.db --dry-run   # preview without deleting
```

**Default horizons:**

| Table           | Env var                     | Default |
|-----------------|-----------------------------|---------|
| `events`        | `RETAIN_EVENTS_DAYS`        | 90 days |
| `verdicts`      | `RETAIN_VERDICTS_DAYS`      | 365 days |
| `scores`        | `RETAIN_SCORES_DAYS`        | 365 days |
| `issue_history` | `RETAIN_ISSUE_HISTORY_DAYS` | 90 days |
| `pipeline_runs` | `RETAIN_PIPELINE_RUNS_DAYS` | 365 days |

Events tied to an in-progress pipeline run are never pruned, regardless of age.

**Schedule via cron** (daily at 03:00):

```cron
0 3 * * * python /path/to/loop-monitor/scripts/prune.py --db /path/to/bounty.db
```

## Scripts

### `scripts/release.sh patch|minor|major`

Bumps VERSION, updates CHANGELOG.md, commits, tags, and creates a GitHub release with extracted changelog notes.

```bash
./scripts/release.sh patch   # 0.1.1 → 0.1.2
./scripts/release.sh minor   # 0.1.1 → 0.2.0
./scripts/release.sh major   # 0.1.1 → 1.0.0
```

Requires a clean working tree and `gh` CLI authenticated.

### `scripts/check-version.sh`

Compares the Loop core version in `$LOOP_ROOT/VERSION` against the latest GitHub release of `svv2014/loop`. Prints a notice if Loop core has a newer release. Throttled to once per hour via `/tmp/loop-version-last-notified`.

Wire it into your Loop core startup or a cron job:

```bash
LOOP_ROOT=/path/to/loop ./scripts/check-version.sh
```

### `scripts/dashboard.py` — terminal dashboard

Stdlib-only TUI that polls `/api/active`, `/api/board`, and `/api/feed` and renders Active Workers, Project Status, and the last 5 feed events. Refreshes in place every `--interval` seconds (default 10); `Ctrl+C` exits cleanly. Use `--once` for a single snapshot suitable for piping or screenshots.

```bash
python3 scripts/dashboard.py                       # live, refresh every 10s
python3 scripts/dashboard.py --interval 5          # custom refresh
python3 scripts/dashboard.py --once                # one snapshot, exit 0
python3 scripts/dashboard.py --url http://host:18792 --once
```

## Security

loop-monitor is **designed to bind to `127.0.0.1`**. The bounty event
API has **no authentication**. Don't expose port 18792 to the network.

If you need network exposure, terminate auth at a reverse proxy. See
[SECURITY.md](SECURITY.md) for the full trust model.

## Development

```bash
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 18792 --reload
pytest tests/
```

## Versioning

[Semantic Versioning](https://semver.org). loop-monitor independently
versioned from Loop core; the bounty event API contract is shared and
versioned separately (currently `1.0`).

## License

[MIT](LICENSE).
