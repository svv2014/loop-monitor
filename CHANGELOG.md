# Changelog

All notable changes to loop-monitor are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

loop-monitor is independently versioned from [Loop core](https://github.com/svv2014/loop).
The shared contract between them is the **bounty event API**, which has
its own version (currently `1.0`) baked into every payload.

## [Unreleased]

## [0.3.0] - 2026-05-14

The "Dope UI" milestone — React/Vite frontend replaces the vanilla-JS
dashboard. Phase 5 cutover landed (#259): React serves at `/`, the
`/v2` mount is removed, all `static/index.html` / `static/js/**` /
`static/css/style.css` deleted. Per-issue cost view (#149), Logs tab
port to React, drawer + URL hash routing, charts panel and Claude
Usage all shipped under this milestone. Operators must run
`cd web && npm run build` before starting the server.

### Changed (BREAKING)
- [LM-123] React/Vite build (static/dist) is now mounted at `/`; legacy `/v2` mount removed. Vanilla-JS dashboard (static/index.html, static/js/**, static/css/style.css) deleted. (#259)
- vite.config.ts `base` flipped to `/` to match the new mount. (#262)

### Added
- [LM-115] Phase 2 · API client, transforms, fixture mode (#151)
- Dope UI phases 0-4 cumulative: visual regression harness, Vite scaffold, Overview / Action Queue / Project Detail / Worker Detail / Logs / Cost screens, drawer + hash routing, charts panel, Claude Usage, NavRail keyboard shortcuts, version badge.

### Fixed
- [LM-126] fix db connection leak — add db_dep() FastAPI dependency + try/finally for bg tasks (#189)

## [0.2.1] - 2026-05-09

A two-week features-and-foundations batch. New dashboard surfaces
(Logs, Action Queue, Claude Usage, terminal dashboard, PR Monitor),
a server-side modularization, baseline lint/type infra, and the
groundwork for the Dope UI React migration.

### Added — dashboard surfaces
- [LM-98] Logs tab and `/api/logs` endpoint with orphan detection (#104)
- [LM-47] Action Queue dashboard tab + API (#94)
- [LM-56] Claude usage panel (#72)
- [LM-50] Per-project PR Monitor endpoint and table (#95)
- [LM-55] `/api/claude_usage` endpoint with env-var config and cached Anthropic admin source (#101)
- [LM-53] Per-project cycle time panel + 7-day sparkline (#61)
- [LM-62] `/api/events_graph` — 24h bucketed event counts by stage (#71)
- [LM-30] Feed filter controls — role and status filtering (#93)
- [LM-28] Monitor version + loop_id filter selector in header (#76)
- [LM-96] Terminal dashboard script (#97)
- [LM-102] git_sha in `/api/health` (#103)

### Added — Dope UI migration foundations
- [LM-114] Vite + React + TypeScript scaffold (#131)
- [LM-115] API client, transforms, fixture mode (early)
- [LM-117] Phase 3.2 Action Queue screen (React port, partial; full screen lands in v0.3)
- [LM-120] Loop selector + version badge in TopBar (React) (#139)
- [LM-136] Stuck detector panel (#145)
- Migration plan + design standards + ADRs documented (#112)

### Added — server / infra
- [LM-83] Split `server.py` into `server/` package (routes, models, db, helpers) (#87)
- [LM-79] DB migrations framework (replaces CREATE IF NOT EXISTS pattern) (#86)
- [LM-85] Modularized `static/index.html` — extracted JS into `static/js/` ES modules (#90)
- [LM-81] Baseline linting + type-checking (ruff + mypy + pre-commit) (#91)
- [LM-82] Nightly retention script to prune old `bounty.db` rows (#92)
- [LM-39] Enable WAL mode, busy_timeout, OperationalError logging (#99)
- [LM-84] Split `test_server.py` into per-area test modules (#88)
- [LM-80] Remove dead shell scripts, add `*.db` to `.gitignore`, document `run.sh` (#89)

### Drafts (carried forward)
- [LM-18] Timeline: per-event cumulative time and feed age_seconds (#20)
- [LM-19] Mark PR/issue as finished; report open→close lifecycle time (#23)

### Note on versioning

Pre-1.0 patch number (v0.2.1) was chosen deliberately — the Dope UI
React migration is mid-flight and will be the headline of v0.3.0 once
all phase-3 screens land. v0.2.1 captures the genuine new functionality
and infra work that's already in production behavior on the legacy UI.

## [0.1.1] - 2026-04-27

Catch-up release. v0.1.0 shipped a stale embedded copy of bounty-monitor
(308-line server, 8 endpoints) instead of the latest standalone content
(683-line server, 18 endpoints). This release closes the gap.

### Added

- `/api/history`, `/api/active`, `/api/verdicts`, `/api/runs` endpoints
- `/api/stats/stages`, `/api/stats/activity`, `/api/stats/rework`,
  `/api/stats/timeline/*` endpoints
- Full dashboard UI (1374-line `static/index.html`) with History, Stats,
  Work Queue tabs
- `lib/` helpers (DB migration + query helpers)
- `scripts/judge.sh` (AI judge that posts PR scorecard comments)
- Role-prompt helpers used by the judge: `planner.sh`, `builder.sh`,
  `reviewer.sh`, `tester.sh`, `reviser.sh`, `merger.sh`
- `requirements.txt` (Python deps pinned)
- `test_server.py` (pytest coverage)

### Changed

- DB filename: `bounties.db` → `bounty.db` (matches latest standalone
  convention; existing v0.1.0 deployments need to migrate or recreate)
- `ReportPayload` accepts BOTH legacy schema (`event_type`,
  `issue_number`, `pr_number`) and v1.0 schema (`event`, `issue_num`,
  `pr_num`) via Pydantic `model_validator` backfill. bounty.sh from
  either era works without changes.


## [0.1.0] - 2026-04-27

Initial public release. loop-monitor is the public rebrand of the
prior loop-monitor companion.

### Added

- **FastAPI dashboard** at `http://127.0.0.1:18792` — live agent status,
  bounty leaderboard, history, judge verdicts.
- **Bounty event API v1.0** — `/api/report` accepts versioned payloads
  from Loop core. Accepts `api: "1.x"`, gracefully ignores unknown
  fields, rejects future major versions with HTTP 426.
- **AI judge** — runs after every merged PR, posts a scorecard comment
  with role-level bounty points and a verdict.
- **History tab** — run table, timeline, stats cards.
- **Work queue tab** — cross-project pipeline backlog with priority.
- **Versioning** — `VERSION` file at repo root; surfaced in
  `/api/health`.
- **Retention + export** — bounty data exportable as CSV/JSON for
  analysis; pruning policy configurable.

[Unreleased]: https://github.com/svv2014/loop-monitor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/svv2014/loop-monitor/releases/tag/v0.1.0
[0.1.1]: https://github.com/svv2014/loop-monitor/releases/tag/v0.1.1
