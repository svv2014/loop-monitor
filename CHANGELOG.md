# Changelog

All notable changes to loop-monitor are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

loop-monitor is independently versioned from [Loop core](https://github.com/svv2014/loop).
The shared contract between them is the **bounty event API**, which has
its own version (currently `1.0`) baked into every payload.

## [Unreleased]

## [0.1.0] - 2026-04-27

Initial public release. loop-monitor is the public rebrand of the
prior bounty-monitor companion.

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
