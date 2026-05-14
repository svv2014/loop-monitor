# loop-monitor — Dashboard for autonomous CI/CD pipelines

> Live agent status, leaderboard, AI judge verdicts, PR scorecards, cycle-time analytics. Bring your own pipeline.

loop-monitor renders any pipeline that emits the simple [bounty event API](#api). It ships with first-class integration for [Loop](https://github.com/svv2014/loop) (the autonomous dev pipeline it was originally built for), but works equally well as the visibility layer for your own CI/CD, autonomous-agent, or build/deploy system. The role vocabulary, project list, and event types are all operator-configurable via yaml — no source patches.

```
┌─────────────────────────────────────────────────────────────┐
│                      LOOP MONITOR                            │
│                http://localhost:18792                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐      │
│  │   Lint   │  │  Build   │  │   Test   │  │ Deploy │      │
│  │ ◉  idle  │  │ ◉  busy  │  │ ◉  idle  │  │ ◉ wait │      │
│  │ 52 pts   │  │ 185 pts  │  │ 120 pts  │  │ 74 pts │      │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘      │
│                                                              │
│  LIVE FEED                           LEADERBOARD             │
│  • ◉ Builder working #35            1. sonnet   185 pts    │
│  • ✓ Test passed #301               2. opus     120 pts    │
│  • ★ Merged #42 → +13 pts           3. gemini    12 pts    │
│                                                              │
│  JUDGE VERDICT (PR #42):                                     │
│  "Clean merge, solid spec, no rework. Full score."           │
└─────────────────────────────────────────────────────────────┘
```

## What it shows

- **Live status** — every stage of your pipeline reports events as it works (`build_start`, `test_done`, `deploy_failed`, etc.). The dashboard renders them in real time.
- **Leaderboard** — points awarded per role per completed unit of work. Useful when comparing models, agents, or strategies.
- **AI judge verdicts** *(optional)* — a downstream scorecard with role-level points and a one-sentence assessment per completed PR / pipeline run.
- **History tab** — full event table, per-ticket timeline, stats cards.
- **Action queue** — cross-project pipeline backlog ordered by attention needed.
- **Cost / cycle-time analytics** — rework factor per ticket, per-stage cycle-time distributions, SLO breach tracking, capacity utilization.
- **Logs panel** — tail your pipeline's handler log files without `ssh`-ing into the box.

## Quickstart

```bash
git clone https://github.com/svv2014/loop-monitor.git
cd loop-monitor
pip install -r requirements.txt
cd web && npm run build && cd ..
cp config/projects.yaml.example config/projects.yaml   # then edit
./run.sh
```

Open http://127.0.0.1:18792.

## Bring your own pipeline

loop-monitor is wire-compatible with any system that can POST a small JSON payload per stage transition. Three configuration files cover the common reuse cases:

### 1. `config/projects.yaml` — the project registry

```yaml
projects:
  web-app:      myorg/web-app
  api-server:   myorg/api-server
  ml-pipeline:  myorg/ml-pipeline
```

Maps each project slug (the value your pipeline POSTs in the `project` field) to a GitHub `owner/repo`. Used for building issue/PR URLs across the dashboard. Lookup chain: `$LOOP_MONITOR_PROJECTS_CONFIG` env override → `./config/projects.yaml` → empty registry (server still runs, links absent).

### 2. `config/roles.yaml` — the role/event vocabulary

```yaml
roles:
  - id: lint
    label: Lint
    color: cyan
  - id: build
    label: Build
    color: blue
  - id: test
    label: Test
    color: amber
  - id: deploy
    label: Deploy
    color: green
```

Defines which stages your pipeline reports and how they display. Allowed colors: `violet`, `blue`, `cyan`, `amber`, `pink`, `green`, `indigo`, `red`, `gray`. Order determines display order in charts and filters. Lookup chain: `$LOOP_MONITOR_ROLES_CONFIG` env override → `./config/roles.yaml` → built-in Loop defaults (`po`, `dev`, `qa`, `reviewer`, `merge`, `judge`).

### 3. The bounty event API — what your pipeline sends

`POST /api/report` once per stage transition (fire-and-forget, server-side errors don't break your pipeline):

```json
{
  "api": "1.0",
  "event": "build_done",
  "role": "build",
  "agent": "ci-runner",
  "model": "gha-ubuntu-22.04",
  "project": "web-app",
  "issue_num": 42,
  "pr_num": 100,
  "detail": "compiled 1247 modules in 38s",
  "timestamp": "2026-05-13T10:32:00Z"
}
```

Field semantics:
- `event` — free-form event type. Convention: `<role>_start` / `<role>_done` / `<role>_failed` so the leaderboard, charts, and judge can group correctly.
- `role` — must match a `roles[].id` in your `roles.yaml` (otherwise it renders as "unknown" with gray color).
- `agent` / `model` — free-form identifiers for the implementation that produced the event. Used to slice the leaderboard.
- `project` — must match a `projects.yaml` slug for issue/PR links to work.
- `issue_num` / `pr_num` — optional; both can be present (an issue's resulting PR).
- `detail` — optional free-form context.

Loop core sends these automatically. For your own pipeline, send them from CI hooks, Lambda functions, container exit traps, etc. — anything that can `curl`.

## Wire it to Loop

If you're running [Loop](https://github.com/svv2014/loop), wire it via `loop.env`:

```bash
LOOP_BOUNTY_URL=http://127.0.0.1:18792
```

That's it. Loop's handlers send events without further config. If loop-monitor is down, the pipeline is unaffected.

## API

### `POST /api/report` — bounty event ingestion (v1.0)

See [Bring your own pipeline](#bring-your-own-pipeline) for the payload shape.

- Accepts `api: "1.x"` — gracefully ignores unknown fields
- Rejects future major versions (`api: "2.x"`) with HTTP 426
- Missing `api` field treated as `"1.0"` legacy

### `GET /api/config/roles` — operator-configured role vocabulary

```json
{
  "roles": [
    {"id": "lint",   "label": "Lint",   "color": "cyan"},
    {"id": "build",  "label": "Build",  "color": "blue"},
    {"id": "test",   "label": "Test",   "color": "amber"},
    {"id": "deploy", "label": "Deploy", "color": "green"}
  ]
}
```

Returns the contents of `config/roles.yaml`, or built-in defaults if unconfigured. The frontend reads this at startup.

### `GET /api/config/projects` — operator-configured project registry

```json
{
  "projects": [
    {"slug": "web-app",    "repo": "myorg/web-app"},
    {"slug": "api-server", "repo": "myorg/api-server"}
  ]
}
```

### `GET /api/health` — monitor status

```json
{
  "status": "ok",
  "monitor_version": "0.1.1",
  "supported_bounty_api": "1.x",
  "core_version_counts": {"0.1.0": 42}
}
```

## Data retention

`bounty.db` grows at ~600 events/day. Run `scripts/prune.py` nightly to keep it bounded.

```bash
python scripts/prune.py --db bounty.db
python scripts/prune.py --db bounty.db --dry-run   # preview without deleting
```

**Default horizons:**

| Table           | Env var                     | Default  |
|-----------------|-----------------------------|----------|
| `events`        | `RETAIN_EVENTS_DAYS`        | 90 days  |
| `verdicts`      | `RETAIN_VERDICTS_DAYS`      | 365 days |
| `scores`        | `RETAIN_SCORES_DAYS`        | 365 days |
| `issue_history` | `RETAIN_ISSUE_HISTORY_DAYS` | 90 days  |
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

### `scripts/dashboard.py` — terminal dashboard

Stdlib-only TUI that polls `/api/active`, `/api/board`, and `/api/feed` and renders Active Workers, Project Status, and the last 5 feed events. Refreshes in place every `--interval` seconds (default 10); `Ctrl+C` exits cleanly. Use `--once` for a single snapshot suitable for piping or screenshots.

```bash
python3 scripts/dashboard.py                       # live, refresh every 10s
python3 scripts/dashboard.py --interval 5          # custom refresh
python3 scripts/dashboard.py --once                # one snapshot, exit 0
python3 scripts/dashboard.py --url http://host:18792 --once
```

## Security

loop-monitor is **designed to bind to `127.0.0.1`**. The bounty event API has **no authentication**. Don't expose port 18792 to the network.

If you need network exposure, terminate auth at a reverse proxy. See [SECURITY.md](SECURITY.md) for the full trust model.

### Logs panel

The dashboard ships a read-only **Logs** tab that tails handler log files from `${LOOP_LOG_DIR:-~/.openclaw/workspace/logs/loop}/loop-<handler>.log` (via `GET /api/logs`). For non-Loop pipelines, override `LOOP_LOG_DIR` to point at your own log directory.

By default the endpoint is **loopback-only**: requests from any host other than `127.0.0.1`/`::1` receive `403 {"error":"logs disabled"}`. To expose the panel (e.g. behind a Tailscale-fronted proxy), set:

```bash
LOOPMON_EXPOSE_LOGS=1
```

**Warning:** handler logs may contain auth tokens, agent stdout (including code snippets), and other potentially sensitive output. loop-monitor performs no secret stripping. If you enable `LOOPMON_EXPOSE_LOGS`, you are responsible for any exposure that results — terminate auth at a reverse proxy, restrict the network, or both.

## Contributing

loop-monitor is **operator-driven** — currently developed by an autonomous pipeline tied to a single operator account. External PRs are not accepted at this time. See [CONTRIBUTING.md](CONTRIBUTING.md) for details and alternatives (file an issue, fork freely under MIT, file security reports via GitHub Security Advisories).

## Development

```bash
pip install -r requirements.txt
cd web && npm run build && cd ..
uvicorn server.app:app --host 127.0.0.1 --port 18792 --reload
pytest tests/
```

## Versioning

[Semantic Versioning](https://semver.org). loop-monitor is independently versioned from Loop core; the bounty event API contract is shared and versioned separately (currently `1.0`).

## License

[MIT](LICENSE).
