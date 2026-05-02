# ADR 0001 — Frontend stack: Vite + React + TypeScript

- **Status:** Accepted
- **Date:** 2026-05-02
- **Decision-makers:** @svv2014

## Context

The current dashboard is vanilla JS modules in `static/js/**` driving a server-rendered `static/index.html` with Chart.js. A new visual design (`design/new-design/`) was delivered as a React 18 + Babel-standalone (in-browser JSX) prototype. We need to choose how to ship it.

The product is expected to keep evolving — more screens, richer interactions, possibly a settings/admin surface, eventually mobile-friendly views — so the frontend stack will see continued growth, not a one-shot port.

## Options considered

1. **In-browser Babel (`@babel/standalone`)** — what the prototype ships as. Zero tooling, JSX compiled per page-load.
2. **Vite + React + TypeScript.** Standard modern frontend toolchain.
3. **Stay vanilla JS, port visuals only.** Copy `styles.css` and HTML structure; keep current architecture.

## Decision

**Option 2: Vite + React 18 + TypeScript.**

Frontend source lives in `web/` at the repo root. Build output is written to `static/dist/` and served by FastAPI via `StaticFiles`. Dev server proxies `/api/*` to the running Python backend.

## Rationale

- **In-browser Babel** is fine for prototypes but degrades as the codebase grows: per-load compile cost (200–500ms cold), no tree-shaking, no type-checking, no npm ecosystem (every dependency must exist as a UMD on a CDN), no production minification, broken stack traces. None of these are acceptable for a long-lived dashboard.
- **Vanilla JS** keeps the Python-only repo, but every additional screen reproduces the boilerplate already visible in `static/js/components/*.js`. The new design assumes React semantics (component composition, `useState`/`useEffect` patterns, screen-level routing, the Tweaks panel's runtime CSS-var system); reproducing those in vanilla JS is busywork that buys nothing.
- **Vite + React + TS** gives HMR for fast iteration, type safety across API payloads and component props, access to npm packages we will want (TanStack Query for polling, recharts or visx for charts, lucide for icons, zod for runtime payload validation), and a real production build. The cost — adding Node/npm to a Python repo — is one-time and isolated to `web/`.

## Consequences

### Positive
- One canonical React + TS toolchain new contributors can join without ramp-up.
- `web/` is independently buildable and testable; doesn't entangle with `server/` lint/test config.
- Clean migration path for future tooling (Storybook, Playwright component tests, etc.).
- Type-checked API client catches backend/frontend drift at compile time.

### Negative
- Repo gains a `package.json`, `node_modules`, and a CI step for the frontend build.
- Contributors need Node ≥ 20. Document in `CONTRIBUTING.md`.
- Two lint configs (ruff for Python, eslint/biome for TS).
- `static/dist/` must be built before `uvicorn` serves it in prod — or built in CI and committed (we won't — see below).

### Neutral
- Build output is **not** committed. CI builds `web/` before packaging. Local dev uses Vite's dev server.

## Implementation notes (non-binding guidance)

- Use **TanStack Query** for the 5-second polling loop. Recommended, not mandated — a plain `useEffect` + `setInterval` is acceptable if a contributor prefers it for a small surface.
- Use **biome** or **eslint + prettier** — pick one in Phase 1 and don't mix.
- Charts: try **recharts** first; fall back to wrapping the existing **Chart.js** if recharts struggles with a specific viz.
- Routing: client-side, screen state in URL hash to match today's deep-link behavior (`#project=…`).
- Styling: design tokens stay in CSS custom properties (see `design/DESIGN_STANDARDS.md`). No CSS-in-JS, no Tailwind, no component libraries.

## Revisit

Re-open this ADR if any of:
- The frontend stops being a single SPA (e.g. embeddable widgets shipped to other surfaces).
- A second product surface (mobile native, CLI dashboard) needs to share UI code.
- TypeScript compile times or bundle size become a real bottleneck.
