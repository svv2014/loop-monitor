# Agent guidance — loop-monitor

## UI changes (`web/src/`)

Read `design/DESIGN_STANDARDS.md` before writing any React code.
It defines color tokens, aesthetic rules, layout grid, and a do/don't list.
Use existing tokens — no inventing colors, paddings, or font sizes.
Justify any deviation explicitly in the PR description.

Visual regression CI (`tests/visual/`) catches major drift, but subtle drift
(wrong padding, hand-rolled link styling, off-token colors) won't fail CI.
Read the standards.

Future UI tickets filed by the operator should include a reference to
`design/DESIGN_STANDARDS.md` in the ticket body so every PR starts from the
same design baseline.

## Server changes (`server/`)

Follow existing route module patterns in `server/routes/`.
Add tests to the appropriate per-area `tests/test_<area>_routes.py` file.

## Schema changes (`bounty.db`)

Document the change in `docs/` and include a backfill / forward-compat note
in the PR description.
