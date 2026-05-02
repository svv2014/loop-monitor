# ADR 0002 — Visual regression via Playwright-Python + pixelmatch

- **Status:** Accepted
- **Date:** 2026-05-02
- **Decision-makers:** @svv2014

## Context

The UI migration (ADR 0001) ports a frozen design prototype (`design/new-design/`) into React, screen by screen. Each port should match the prototype pixel-for-pixel within a tight tolerance. Loop's automated `qa` role cannot judge visual fidelity, so we need a CI-enforced gate.

## Options considered

1. **Human visual review only.** Reviewer opens the PR preview, eyeballs it.
2. **Chromatic / Percy** (hosted visual-diff SaaS).
3. **Playwright-Python + pixelmatch in CI** (self-hosted).
4. **Storybook + Loki / reg-suit.**

## Decision

**Option 3: Playwright-Python + pixelmatch in CI.**

- Reference screenshots live at `design/reference-screenshots/` and are captured once from the frozen prototype.
- Tests at `tests/visual/` render the React app at the same fixed viewport with deterministic fixture data and diff against references.
- Threshold: ≤ 0.5% differing pixels per screen, ignored regions (live timestamps, animation frames) masked explicitly.

## Rationale

- **Human-only** is what option (a) and (b) of the discussion would have been. Loop merges autonomously; expecting every UI PR to wait on a human pulls a team out of the autonomous loop unnecessarily.
- **Chromatic/Percy** are excellent but introduce a paid SaaS dependency in an open-source repo and gate contributors on an external account.
- **Playwright-Python** is the natural choice because the repo is already Python — the visual suite reuses the same `pytest` runner, `requirements.txt`, and CI workflow as the rest of the project. No new language ecosystem.
- **Storybook + Loki** would mean introducing Storybook just for visual tests, which is overkill given we already have a frozen HTML prototype as the source of truth.

## Consequences

### Positive
- Self-hosted, free, open-source-friendly.
- One language for all test code (Python).
- Reference screenshots are reviewable artifacts in git, so the spec is concrete and auditable.
- Loop's `qa` role can run the suite locally and gate its own PRs.

### Negative
- Reference PNGs live in git (some KB per screen × ~6 screens — manageable; LFS not needed yet).
- Font rendering and antialiasing differ between OSes; CI runs on Linux only and references are captured on Linux.
- Animations and "now" timestamps must be masked or the suite goes flaky.

## Implementation notes

- **Capture once:** `python tests/visual/capture_references.py` renders `design/new-design/Pipeline Monitor.html` headless at 1440×900 and writes `design/reference-screenshots/{overview,queue,project,worker}.png`.
- **Fixture mode:** the React app reads `?fixtures=1` and loads the same seeded mock the prototype uses, so renders are deterministic.
- **Mask regions:** elements with `data-vr-mask="true"` (live clocks, the `.dot` pulse, fresh-row flash) are filled with a flat color before diffing.
- **Threshold:** start at 0.5% pixel diff, tighten if too lenient in practice.
- **CI:** `tests/visual/` runs on PRs labeled `ui-migration` and `frontend`. Failure attaches a diff PNG as an artifact.

## Revisit

Re-open if:
- Cross-OS rendering differences make the suite chronically flaky (move to a containerized renderer).
- The reference set grows beyond ~50 screens (consider git-lfs or hosted snapshots).
- We add a real component library / Storybook (visual tests should live alongside stories).
