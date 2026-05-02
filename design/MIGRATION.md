# Loop Monitor — UI Migration Plan

Replace the vanilla-JS dashboard (`static/index.html` + `static/js/**`) with a React app modelled on the prototype in `design/new-design/`. Backend (Python / FastAPI) is untouched.

**Stack: Vite + React 18 + TypeScript.** Decision recorded in [`docs/adr/0001-frontend-stack.md`](../docs/adr/0001-frontend-stack.md).

**Visual-regression gate.** Phases that touch visible screens require a visual-diff CI check against frozen reference screenshots from the prototype. Decision recorded in [`docs/adr/0002-visual-regression.md`](../docs/adr/0002-visual-regression.md).

---

## Layout

```
loop-monitor/
├── web/                      ← new React source (Vite project)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── lib/
│       │   ├── api.ts                  ← thin client over /api/*
│       │   ├── tokens.css              ← ports design/new-design/styles.css verbatim
│       │   └── transforms.ts           ← buildLeaderboard / buildProjectStatus / build24hBuckets
│       ├── components/                 ← Logo, TopBar, NavRail, RoleTag, EventGlyph
│       ├── panels/                     ← NowStrip, Activity24h, ProjectCard, Leaderboard, ActivityFeed
│       └── screens/                    ← Overview, Queue, ProjectDetail, WorkerDetail
├── static/dist/              ← Vite build output (gitignored), served by FastAPI at /
├── design/
│   ├── new-design/           ← FROZEN reference prototype — do not edit
│   ├── DESIGN_STANDARDS.md
│   ├── MIGRATION.md          ← this file
│   ├── TICKETS.md            ← draft issues
│   └── reference-screenshots/ ← PNG fixtures captured from the prototype
├── tests/visual/             ← Playwright-Python visual-diff suite
└── docs/adr/
    ├── 0001-frontend-stack.md
    └── 0002-visual-regression.md
```

Dev: `cd web && npm run dev` (Vite proxies `/api/*` to `http://127.0.0.1:18792`).
Prod: `npm run build` → `static/dist/` → FastAPI serves it via `StaticFiles`.

---

## Mapping: prototype screens → real APIs

| Prototype screen | Real endpoint(s) |
|---|---|
| Overview · NowStrip | `GET /api/active` |
| Overview · 24h Activity | `GET /api/events_graph?window=24` |
| Overview · Project status | `GET /api/status` + `/api/projects` + `/api/active` |
| Overview · Leaderboard | `GET /api/board` |
| Overview · Activity feed | `GET /api/feed` |
| Overview · Completed jobs | `GET /api/history` |
| Action Queue | `GET /api/action_queue` |
| Project detail | `GET /api/runs/:project` + `/api/pr_monitor/:project` |
| Worker detail | client-side rollup of `/api/feed` |

No backend changes in this migration. Anything that needs a new endpoint becomes a separate, post-migration ticket.

---

## Phased rollout

Each phase = one PR. Old UI stays live until phase 5.

### Phase 0 — Visual-diff harness (prerequisite)
- Add Playwright-Python to dev deps. New `tests/visual/` suite.
- Render `design/new-design/Pipeline Monitor.html` headless at fixed viewport (1440×900) and capture per-screen reference PNGs into `design/reference-screenshots/`.
- CI workflow `visual-diff.yml` that, given a PR with the `ui-migration` label, builds `web/`, renders the same screens against the same fixtures, and fails if pixel-diff > threshold.
- Defines a **fixture mode** flag (`?fixtures=1` or env var) that tells the React app to load deterministic mocks instead of hitting the live API. Fixtures are ported from the prototype's seeded `data.js`.

### Phase 1 — Scaffold (no behavior change for users)
- Create `web/` with Vite + React + TS skeleton.
- Port `design/new-design/styles.css` to `web/src/lib/tokens.css` unchanged.
- Wire FastAPI to serve `static/dist/` at `/v2`. `/` keeps the old UI.
- Render an empty shell (Logo + TopBar + NavRail + main area) at `/v2`.

### Phase 2 — API client + transforms
- Implement `web/src/lib/api.ts` calling the same endpoints as `static/js/api.js` does today.
- Add **TanStack Query** for the polling loop (5s refetch, matching today's cadence).
- Port pure helpers `buildLeaderboard` / `buildProjectStatus` / `build24hBuckets` from `design/new-design/data.js` into `web/src/lib/transforms.ts` with TS types.
- Define the `LoopEvent` / `Worker` / `Project` etc. types once, in `web/src/lib/types.ts`.

### Phase 3 — Port screens (one screen = one PR, gated by visual-diff)
Order chosen so each merge ships a working dashboard:
1. **Overview**
2. **Action Queue**
3. **Project detail** (includes PR Monitor sub-panel from old UI)
4. **Worker detail** (pure client-side rollup)

Each PR also deletes the old vanilla-JS counterpart in `static/js/components/`.

### Phase 4 — Carry-over features the prototype is missing
- **Loop selector** in TopBar; thread `loop_id` through `api.ts`.
- **Charts** (`Events/Day`, `Total Points by Project`, `Avg Minutes per Stage`, `Rework Rate`) — recharts or keep Chart.js via a thin React wrapper.
- **Claude Usage panel.**
- **Drawer / timeline** triggered from feed rows.
- **URL hash routing** for deep links (matches today's `#project=…`).
- **Action Queue filters** (project / reason / loop) and sortable columns.
- **Version badge** with git SHA from `/api/health`.

### Phase 5 — Cutover
- Repoint `/` to `static/dist/`. Delete `static/index.html` and `static/js/**`.
- Drop `static/css/style.css` if nothing else imports it.
- Update `README.md` and `CHANGELOG.md`.

---

## Critical files

**Read-only references**
- `design/new-design/` — frozen prototype; visual source of truth
- `design/DESIGN_STANDARDS.md` — token system and component rules
- `static/js/api.js` — exact API surface the new client must replicate
- `server/routes/*.py` — payload shapes; do not change

**Created**
- `web/**`, `tests/visual/**`, `design/reference-screenshots/**`
- `docs/adr/0001-frontend-stack.md`, `docs/adr/0002-visual-regression.md`

**Deleted at phase 5**
- `static/index.html`, `static/js/**`, possibly `static/css/style.css`

---

## Verification

Per phase:
- `pytest tests/` green (backend untouched).
- `pytest tests/visual/` green (visual-diff under threshold).
- Manual smoke at `/v2`: every screen loads, polls every 5s, no console errors.

End-to-end at phase 5:
- Feature parity check against today's `/`: loop filter, charts, drawer, PR monitor, Claude usage, version badge.
- Lighthouse score not worse than current.
