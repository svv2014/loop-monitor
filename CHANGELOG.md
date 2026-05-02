# Changelog

All notable changes to loop-monitor are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

loop-monitor is independently versioned from [Loop core](https://github.com/svv2014/loop).
The shared contract between them is the **bounty event API**, which has
its own version (currently `1.0`) baked into every payload.

## [Unreleased]


### Changed
- Draft: [LM-18] Timeline: per-event cumulative time and feed age_seconds (#20)
- Draft: [LM-19] Mark PR/issue as finished; report open→close lifecycle time (#23)
- [LM-62] Add GET /api/events_graph — 24h bucketed event counts by stage (#71)
- [LM-56] Add Claude usage panel to dashboard (#72)
- [LM-28] UI: show monitor version in header; add loop_id filter selector (#76)
- [LM-79] Add DB migrations framework (replace CREATE IF NOT EXISTS pattern) (#86)
- [LM-80] Remove dead shell scripts, add *.db to .gitignore, document run.sh (#89)
- [LM-85] Modularize static/index.html — extract JS into static/js/ ES modules (#90)
- [LM-81] Add baseline linting + type-checking (ruff + mypy + pre-commit) (#91)
- [LM-82] Add nightly retention script to prune old bounty.db rows (#92)
- [LM-30] Feed filter controls — role and status filtering (#93)
- [LM-47] Add Action Queue dashboard tab and API (#94)
- [LM-53] Add per-project cycle time panel and 7-day sparkline to home dashboard (#61)
- [LM-83] Split server.py into server/ package (routes, models, db, helpers) (#87)
- [LM-96] Add terminal dashboard script (#97)
- [LM-102] add git_sha to /api/health (#103)
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
