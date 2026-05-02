# Frozen Reference Prototype — DO NOT EDIT

This directory is the **canonical visual reference** for the loop-monitor React migration.

It contains the design as delivered: a React 18 + Babel-standalone prototype with seeded mock data. It is not a build target. Nothing here is shipped to users.

## What this is for

- **Source of truth for visuals.** When porting a screen into `web/src/`, the rendered output of these files is what your PR is being diffed against.
- **Reference screenshots.** `tests/visual/capture_references.py` renders this prototype headless and writes PNGs to `design/reference-screenshots/` — those PNGs are what CI compares your build against.
- **Design exploration archive.** If a future redesign happens, replace this directory wholesale with the new prototype (in a single PR), update reference screenshots, and re-run the migration playbook.

## Rules

- **Do not edit files here.** Bug in the prototype? File an issue and fix the *port* in `web/src/`, not the source of truth.
- **Do not import from here at runtime.** The shipped app lives entirely in `web/`. These files are reference material only.
- **Do not delete during migration.** Phase 5 (cutover) does not touch this directory. It stays for the duration of the project as the visual contract.

## Files

| File | Purpose |
|---|---|
| `Pipeline Monitor.html` | entry point; loads React UMD + Babel-standalone |
| `app.jsx` | top-level App, screen routing, Tweaks wiring, mock event simulator |
| `screens.jsx` | OverviewScreen, QueueScreen, ProjectDetail, WorkerDetail |
| `panels.jsx` | NowStrip, Activity24h, ProjectCard, Leaderboard, ActivityFeed |
| `components.jsx` | Logo, TopBar, NavRail, RoleTag, EventGlyph + helpers |
| `tweaks-panel.jsx` | runtime density / accent / grain / live-speed controls |
| `data.js` | seeded mock event stream + helper transforms |
| `styles.css` | design tokens + base styles (the spec) |
| `uploads/` | static reference images (e.g. annotated screenshots) |

## Viewing it locally

```bash
# Any static server works
cd design/new-design
python -m http.server 8000
# open http://localhost:8000/Pipeline%20Monitor.html
```

## Related docs

- [`design/DESIGN_STANDARDS.md`](../DESIGN_STANDARDS.md) — the rules a port must follow
- [`design/MIGRATION.md`](../MIGRATION.md) — phased rollout plan
- [`docs/adr/0001-frontend-stack.md`](../../docs/adr/0001-frontend-stack.md) — Vite + React + TS decision
- [`docs/adr/0002-visual-regression.md`](../../docs/adr/0002-visual-regression.md) — visual-diff CI gate
