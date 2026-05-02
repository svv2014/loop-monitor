---
name: UI migration task
about: A scoped chunk of the React UI migration. Designed to be picked up by Loop or a human contributor.
title: "[ui] "
labels: ui-migration, frontend
assignees: ""
---

<!--
  Before filing, read:
  - design/MIGRATION.md         (phased plan)
  - design/DESIGN_STANDARDS.md  (token system + component rules)
  - design/new-design/README.md (frozen reference prototype)
  - docs/adr/0001-frontend-stack.md
  - docs/adr/0002-visual-regression.md

  Loop's `dev` role: implement only what's listed. Do not refactor outside the
  files listed under "In scope". The "Out of scope" section is binding.

  TODO(vadym): if your loop config maps roles to GitHub labels (e.g. `loop-po`,
  `loop-dev`, `loop-qa`), add them here.
-->

## Goal

<!-- One sentence. What does success look like? -->

## Phase

<!-- Phase 0 / 1 / 2 / 3.{overview|queue|project|worker} / 4.{feature} / 5 -->

## Context

<!-- Why this ticket exists. Link the migration phase. Reference any prior PR
     in the same phase. -->

## In scope (files Loop's `dev` is allowed to touch)

- `web/src/...`
- `tests/visual/...`

## Out of scope

- Backend (`server/**`) — do not modify
- Other screens not listed above
- Adding npm dependencies beyond those already in `web/package.json` (open a separate ticket)
- New design tokens (use what's in `web/src/lib/tokens.css`)

## Visual reference

<!-- Which files in design/new-design/ does this port? -->

- `design/new-design/screens.jsx` — section `<Name>`
- `design/new-design/panels.jsx` — `<Component>`

## API endpoints used

<!-- Reference design/MIGRATION.md "Mapping" section. -->

- `GET /api/...`

## Acceptance criteria

- [ ] Screen renders at `/v2` against the live backend
- [ ] All tokens / paddings / fonts come from `tokens.css`; no hard-coded values
- [ ] Renders correctly at all three density settings (`compact` / `cozy` / `roomy`)
- [ ] Renders correctly with each accent color (green / amber / cyan / violet)
- [ ] Empty, loading, and error states implemented (not just happy path)
- [ ] Keyboard reachable (Tab / Enter / Esc as appropriate)
- [ ] Visual-diff CI passes (≤ 0.5% pixel diff vs `design/reference-screenshots/<screen>.png`)
- [ ] No new TypeScript errors (`npm run typecheck` clean)
- [ ] No new lint errors
- [ ] `pytest tests/` green
- [ ] PR description includes a screenshot of the new screen

## Notes for reviewer

<!-- What should the human reviewer pay extra attention to? E.g. "this is the
     first ticket that introduces TanStack Query — review the cache key shape." -->
