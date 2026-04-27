# loop-monitor roadmap

## Shipped — v0.1.0

- FastAPI dashboard (live status, leaderboard, history, work queue)
- Bounty event API v1.0 with version negotiation
- AI judge with PR scorecard comments
- SQLite-backed history with retention + export

## v0.1.x — incremental polish

- Dashboard screenshot for README
- Mobile-responsive CSS pass
- Configurable port via env (currently hardcoded `18792`)
- Stronger graceful-handling of unknown bounty event fields

## v0.2.0 — quality + observability

- Authenticated bounty submission (HMAC-signed token)
- Multi-host bounty event aggregation (run multiple Loop cores into
  one monitor)
- Telemetry endpoint exposing core_version distribution

## v0.3.0 — analytics

- Cohort comparisons (rework rates by agent, by model, by day)
- Cost tracking (token spend per bounty event)
- Anomaly alerts (sudden spike in qa_fail rate)

## v1.0.0 — stable

API and DB schema stable.
