# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1 | ❌ |

## Reporting vulnerabilities

Use [GitHub Security Advisories](https://github.com/svv2014/loop-monitor/security/advisories/new).
**Don't open a public issue for sensitive reports.**

## Trust model

loop-monitor is **designed to bind to `127.0.0.1`** — the localhost
loopback interface — not a public network. The bounty event API has
**no authentication** by default; trust is enforced by network
isolation.

**Don't expose port 18792 to the internet** without adding an auth
proxy. If you need network exposure, terminate TLS + auth at a reverse
proxy (nginx, caddy) in front of loop-monitor.

## Surfaces

- `POST /api/report` — versioned bounty event ingestion (1.0). Accepts
  `api: "1.x"`, rejects future majors with HTTP 426. No auth.
- `GET /api/health` — server status + version. Read-only. No auth.
- Static dashboard at `/` — read-only HTML.
- SQLite DB stores bounty history; readable by any process with file
  access.

## Out of scope

- Authenticated bounty event submission (planned; track via roadmap)
- Multi-tenant support (one operator, one machine)

For Loop core security, see [`svv2014/loop`'s SECURITY.md](https://github.com/svv2014/loop/blob/main/SECURITY.md).
