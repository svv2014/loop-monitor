# Changelog

All notable changes to loop-monitor are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

loop-monitor is independently versioned from [Loop core](https://github.com/svv2014/loop).
The shared contract between them is the **bounty event API**, which has
its own version (currently `1.0`) baked into every payload.

## [Unreleased]

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
