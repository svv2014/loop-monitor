# UI Migration — Draft Tickets

Drafts of GitHub issues to be filed against the milestone **`Dope UI`**.

Labels used: `ui-migration`, `frontend`, `design-system`, `good-first-issue`, `infra`, `needs-human-visual-review`.

File these with `gh issue create -F <body>.md -l <labels>` after review. Order matters — phase 0 and 1 are prerequisites for everything else; phase 2 unlocks phase 3; phase 3 screens can land in any order but each requires phase 2 to be merged.

---

## #LM-A — Phase 0 · Visual-regression harness

**Labels:** `ui-migration`, `infra`, `frontend`

**Goal.** Stand up a Playwright-Python visual-diff suite that gates UI migration PRs.

**In scope.**
- Add `playwright`, `pytest-playwright`, `pixelmatch` (or equivalent) to dev requirements.
- New `tests/visual/` package with: `conftest.py` (browser/viewport fixtures), `capture_references.py` (one-shot script to capture references from `design/new-design/`), `test_screens.py` (PR-time diff tests).
- Capture initial references for: `overview`, `queue`, `project`, `worker` → `design/reference-screenshots/`.
- New CI workflow `.github/workflows/visual-diff.yml` that runs on PRs labeled `ui-migration`.
- Mask regions documented (live clocks, pulse dots, fresh-row flash).

**Out of scope.** Any change to `web/` (doesn't exist yet) or `static/js/`.

**Acceptance.**
- [ ] `python tests/visual/capture_references.py` produces 4 PNGs.
- [ ] `pytest tests/visual/` is green when run against the prototype itself (sanity baseline).
- [ ] CI workflow attaches a diff PNG as an artifact on failure.
- [ ] README in `tests/visual/` explains how to update references when the prototype intentionally changes.

**References.** `docs/adr/0002-visual-regression.md`.

---

## #LM-B — Phase 1 · Vite + React + TS scaffold

**Labels:** `ui-migration`, `frontend`, `infra`

**Goal.** Add `web/` to the repo and serve an empty React shell at `/v2`.

**In scope.**
- `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`.
- Port `design/new-design/styles.css` verbatim to `web/src/lib/tokens.css`.
- Port `Logo`, `TopBar`, `NavRail` from `design/new-design/components.jsx` to TS — empty `main` content area is fine for this PR.
- Vite dev server proxies `/api/*` to `http://127.0.0.1:18792`.
- FastAPI mounts `static/dist/` at `/v2` (only when the directory exists; `/` keeps the old UI).
- `.gitignore` updates: `web/node_modules`, `static/dist/`.
- CI: add `npm ci && npm run build && npm run typecheck` for `web/`.
- `CONTRIBUTING.md` gains a **Frontend** section pointing at `web/README.md`.

**Out of scope.** Any data fetching, any screen content, the Tweaks panel.

**Acceptance.**
- [ ] `cd web && npm run dev` works; `/v2` shows shell only.
- [ ] `npm run build` produces `static/dist/` and FastAPI serves it.
- [ ] `npm run typecheck` clean.
- [ ] No regression on `/` (old UI unchanged).

**References.** `docs/adr/0001-frontend-stack.md`, `design/MIGRATION.md` (Phase 1).

---

## #LM-C — Phase 2 · API client, transforms, fixture mode

**Labels:** `ui-migration`, `frontend`

**Goal.** Wire the React shell to real APIs and to deterministic fixtures.

**In scope.**
- `web/src/lib/types.ts` — `LoopEvent`, `Worker`, `Project`, `QueueItem`, etc.
- `web/src/lib/api.ts` — fetch functions for every endpoint listed in `design/MIGRATION.md` "Mapping".
- TanStack Query installed and wired: 5-second `refetchInterval` for live endpoints.
- `web/src/lib/transforms.ts` — TS port of `buildLeaderboard`, `buildProjectStatus`, `build24hBuckets` from `design/new-design/data.js`.
- **Fixture mode**: when `?fixtures=1` is present, `api.ts` returns the same seeded data the prototype uses (port the seeded RNG + history builder from `data.js`).
- The shell at `/v2` shows live event count and connection status in `TopBar` (smoke-test for the wiring).

**Out of scope.** Any screen content beyond TopBar liveness.

**Acceptance.**
- [ ] DevTools shows the expected `/api/*` calls every 5s.
- [ ] `?fixtures=1` makes zero network calls and renders deterministically.
- [ ] All transform functions have unit tests (`web/src/lib/transforms.test.ts`).
- [ ] `npm run typecheck` clean.

**References.** `static/js/api.js` (current API surface to mirror), `design/MIGRATION.md` (Phase 2).

---

## #LM-D — Phase 3.1 · Overview screen

**Labels:** `ui-migration`, `frontend`, `needs-human-visual-review`

**Goal.** Port the Overview screen end-to-end. Visual diff must pass.

**In scope.**
- `web/src/panels/{NowStrip,Activity24h,ProjectCard,Leaderboard,ActivityFeed}.tsx`.
- `web/src/screens/Overview.tsx`.
- Wire to live data via `api.ts`.
- Delete `static/js/components/{stats,board,feed}.js` and the corresponding `<section>` blocks in `static/index.html` — but only if old UI still renders without them. (If not, leave deletion to phase 5.)

**Out of scope.** Any other screen. URL hash routing. The Drawer.

**Acceptance.** All boxes from the issue template, plus visual-diff against `design/reference-screenshots/overview.png` ≤ 0.5%.

**References.** `design/new-design/screens.jsx` (`OverviewScreen`), `design/new-design/panels.jsx`.

---

## #LM-E — Phase 3.2 · Action Queue screen

**Labels:** `ui-migration`, `frontend`, `needs-human-visual-review`

**Goal.** Port `QueueScreen` and wire to `/api/action_queue`.

**In scope.**
- `web/src/screens/Queue.tsx`.
- Filters (project / reason / loop) and sortable columns from the **current** `static/js/components/action_queue.js` — these are not in the prototype but are existing functionality and must be preserved.
- Delete `static/js/components/action_queue.js`.

**Out of scope.** Other screens.

**Acceptance.** All boxes from the issue template + visual-diff against `queue.png` ≤ 0.5%. Filters and sort behave identically to current `/`.

---

## #LM-F — Phase 3.3 · Project Detail screen (incl. PR Monitor)

**Labels:** `ui-migration`, `frontend`, `needs-human-visual-review`

**Goal.** Port `ProjectDetail` and the existing PR Monitor sub-panel.

**In scope.**
- `web/src/screens/ProjectDetail.tsx` with the prototype's KPI strip, issue rollup, points-by-role chart, event stream.
- **PR Monitor sub-panel** — port the table from `static/js/components/runs.js`. This is not in the prototype; design it consistent with `DESIGN_STANDARDS.md` and add a reference screenshot for it (`project-pr-monitor.png`).
- URL hash routing: `#project=<id>` selects and switches screen.

**Out of scope.** Worker detail.

**Acceptance.** Visual-diff for the prototype-covered region ≤ 0.5%; PR Monitor passes design-standards review.

---

## #LM-G — Phase 3.4 · Worker Detail screen

**Labels:** `ui-migration`, `frontend`, `needs-human-visual-review`

**Goal.** Port `WorkerDetail`. Pure client-side rollup of `/api/feed`.

**In scope.**
- `web/src/screens/WorkerDetail.tsx`.
- Keyboard shortcut `4` switches to this screen.
- Delete `static/js/components/feed.js` if Overview no longer needs it (likely already removed in #LM-D).

**Out of scope.** New backend endpoints.

**Acceptance.** Visual-diff vs `worker.png` ≤ 0.5%.

---

## #LM-H — Phase 4.1 · Loop selector + version badge in TopBar

**Labels:** `ui-migration`, `frontend`

**Goal.** Restore the loop filter and version-with-git-SHA badge from the current UI.

**In scope.**
- `TopBar` gains a `<select>` of loops sourced from `/api/projects` (or wherever today's `header.js` reads loops from).
- `loop_id` threaded through every TanStack Query key.
- Version badge reads from `/api/health`.

**Out of scope.** Anything else.

**Acceptance.** Switching loop refetches every screen. SHA visible.

---

## #LM-I — Phase 4.2 · Charts panel + Claude Usage

**Labels:** `ui-migration`, `frontend`

**Goal.** Port the four charts (`Events/Day`, `Total Points by Project`, `Avg Minutes per Stage`, `Rework Rate`) and the Claude Usage panel.

**In scope.**
- `web/src/panels/Charts.tsx` using **recharts** (or, if recharts struggles, wrap Chart.js).
- `web/src/panels/ClaudeUsage.tsx` from `static/js/components/claude_usage.js`.
- Place on Overview or in a new `Stats` screen — propose in PR description, decide in review.

**Out of scope.** New chart types.

**Acceptance.** Visual parity with current `/` for each chart at the same data.

---

## #LM-J — Phase 4.3 · Drawer / timeline + URL hash routing

**Labels:** `ui-migration`, `frontend`

**Goal.** Port the timeline drawer (`#timeline-drawer` in current `index.html`) and full hash-based deep-linking.

**In scope.**
- `web/src/components/Drawer.tsx` (focus trap, Esc to close, `aria-modal`).
- Click handlers on feed rows / project cards open the drawer.
- Hash routing covers all screens + selected project + open drawer state.

**Out of scope.** Any new endpoints; the drawer reads existing `/api/runs/:project`.

**Acceptance.** Deep-linking parity with current `/`. Keyboard nav works.

---

## #LM-K — Phase 5 · Cutover + cleanup

**Labels:** `ui-migration`, `infra`

**Goal.** Move new UI to `/`. Delete old UI.

**In scope.**
- FastAPI: `static/dist/` mounted at `/`. `/v2` removed.
- Delete `static/index.html`, `static/css/style.css` (if unused), `static/js/**`.
- Update `README.md` (screenshot, dev instructions for the frontend), `CHANGELOG.md`.

**Out of scope.** Any feature changes.

**Acceptance.** Repo is clean of old UI. All tests green. README accurate.

---

## Filing checklist (for whoever runs `gh issue create`)

- [ ] Milestone `Dope UI` exists.
- [ ] Labels `ui-migration`, `frontend`, `design-system`, `infra`, `needs-human-visual-review` exist.
- [ ] File issues **in order**: A → B → C → D → E → F → G → H → I → J → K.
- [ ] Each issue body uses `.github/ISSUE_TEMPLATE/ui-migration-task.md` as the structure.
- [ ] After filing, add a tracking issue (`Dope UI — tracking`) with a checklist linking to all of the above.
