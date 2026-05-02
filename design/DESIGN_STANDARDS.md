# Loop Monitor — Design Standards

The visual and structural rules for the dashboard UI. Anything new you build should follow these or explicitly justify why it doesn't.

Source of truth for tokens: `static/v2/styles.css` (after migration; currently `design/new-design/styles.css`).

---

## 1. Aesthetic

**Terminal / control-room.** Dense, monospaced, hairline borders, near-black surfaces, one accent. No drop shadows, no rounded corners larger than 4px, no gradients except the one ambient page glow. Information density beats whitespace; whitespace is earned, not default.

If a design choice would feel at home in a Stripe marketing page, it's wrong here. If it would feel at home in `htop`, Datadog, or a Bloomberg terminal, it's right.

---

## 2. Color tokens (use these — do not invent)

All colors are OKLCH. Defined as CSS custom properties on `:root`.

### Surfaces (cool near-black, ascending lightness)
- `--bg`        — page background
- `--bg-1`      — panel / card surface
- `--bg-2`      — raised / hover surface
- `--bg-3`      — top-most surface (drawers, popovers)
- `--border`    — default hairline
- `--border-strong` — hover / active border

### Text
- `--fg`   — primary
- `--fg-2` — secondary
- `--fg-3` — muted
- `--fg-4` — dim / disabled

### Brand accent (single, swappable via Tweaks)
- `--accent` / `--accent-2` / `--accent-fg`
- Default is terminal green. The Tweaks panel can swap to amber / cyan / violet — any new component must read from the var, never the literal value.

### Status
- `--pass` / `--fail` / `--warn` / `--info`

### Roles (constant lightness ~0.74, chroma ~0.13–0.16)
- `--role-po` (violet), `--role-dev` (cyan-blue), `--role-qa` (amber), `--role-reviewer` (pink), `--role-merge` (green), `--role-judge` (indigo)
- A role tint is the **only** color allowed for role identification. Don't reuse role colors for unrelated semantics.

**Rules**
- Never use raw hex/rgb/hsl in a component. Reference a token.
- Don't introduce new tokens for one-offs. If a value shows up twice, then promote it.
- Opacity overlays use `oklch(L C H / α)` inline — avoid `rgba`.

---

## 3. Typography

- Sans: **Geist** (`--font-sans`)
- Mono: **JetBrains Mono** (`--font-mono`)
- Font-feature-settings on body: `'cv11', 'ss01'`. Numbers always use `font-variant-numeric: tabular-nums` — apply via `.num` class.

### When to use mono
- All numbers, IDs, durations, timestamps, hashes, event names, model names, project slugs.
- All `.tag`, `.btn`, `.panel-h` labels.
- Anything that benefits from a fixed grid.

### When to use sans
- Long-form text, titles, descriptions.

### Sizes
- Body default: **12px**. Don't go below 10px except for ticks/legends.
- Section heads (`.panel-h`, `.screen-h h1`): **10–13px** uppercase, letter-spacing ~0.08–0.12em.
- Hero numbers: 20–28px, `--font-mono`, `tabular-nums`.

---

## 4. Density

Density is a runtime variable, not a stylesheet branch.

- Padding tokens scale via `--d` multiplier (0.85 / 1 / 1.15).
- Use `var(--pad-1..5)` for any padding/gap. **Never hard-code `padding: 12px`.**
- A new component must look correct at all three density settings.

---

## 5. Layout grammar

### App shell
Fixed grid: `56px` left nav rail, `36px` top bar, single scrolling main pane. Don't add a second sidebar; if you need one, propose a layout change.

### Panels
- `.panel` = `bg-1` + 1px `border`, no radius.
- Every panel has a `.panel-h` header: small uppercase mono label on the left, optional `.actions` cluster on the right.
- Borders are **hairline (1px)**. Never 2px+ except for the active-nav stripe and `proj-card.busy`.

### Grids
- 12-col not used. We compose with explicit `grid-template-columns` per region.
- Common patterns:
  - Two-column with right rail: `1fr 360px`
  - Auto-fit cards: `repeat(auto-fill, minmax(180px, 1fr))` with `gap: 1` and `background: var(--border)` (the hairlines come from the gap)
  - KPI strip: `repeat(N, 1fr)` with `border-right` hairlines per cell

### Spacing
- Between sibling panels in main: `gap: var(--pad-3)`.
- Inside a panel body: `padding: var(--pad-3) var(--pad-4)` for prose, `0` for tables and feed lists (the rows handle their own padding).

---

## 6. Components — the canonical set

If you find yourself building one of these, use the existing implementation. Don't fork.

| Component | Purpose | File |
|---|---|---|
| `Logo` | corner glyph | `components.jsx` |
| `TopBar` | live status + version + clock | `components.jsx` |
| `NavRail` | left icon nav with hover tooltips | `components.jsx` |
| `RoleTag` | role chip | `components.jsx` |
| `EventGlyph` | one-char event symbol with role color | `components.jsx` |
| `NowStrip` | hero strip of currently-running workers | `panels.jsx` |
| `Activity24h` | stacked-by-role hourly bar chart | `panels.jsx` |
| `ProjectCard` | one tile in the project grid | `panels.jsx` |
| `Leaderboard` | role/agent points table | `panels.jsx` |
| `ActivityFeed` | filterable rolling event list | `panels.jsx` |
| `TweaksPanel` | density / accent / live-speed / grain | `tweaks-panel.jsx` |

Atoms: `.btn`, `.btn.primary`, `.tag`, `.tag.solid`, `.feed-row`, `.feed-row.fresh`, `.status-dot.{idle,busy,fail}`, `.kbd`, `.cmdline`, `.ticker`.

---

## 7. Tables

- Class: `table.t`. Always use this. No bespoke table styles.
- Header cells (`th`): mono, 10px, uppercase, sticky, on `bg-1`.
- Row hover: subtle `oklch(1 0 0 / 0.02)` overlay (already in CSS).
- Right-align numeric columns; tag with `.num`.
- Don't put borders on every cell — `border-bottom` per row only.

---

## 8. Motion

Sparingly. Motion exists to confirm state changes, never to entertain.

- New row in feed: `.fresh` flash (1.2s, accent → transparent). Only on the topmost row, only once.
- Live status: `.dot` pulse (2s loop) — exactly one per screen, in the TopBar/NowStrip.
- Worker beat: `heartbeat` (1.4s) on the per-worker pulse.
- Hover transitions: 150ms on `color`, `background`, `border-color`. Nothing else animates on hover.
- No page-transition animations. Screens swap instantly.
- `prefers-reduced-motion`: any new animation must check it and degrade.

---

## 9. Iconography

- 18px line icons in `NavRail`, `strokeWidth="1.5"`, `currentColor`. Inline SVG only — no icon-font dependency.
- Event glyphs are typographic (`◆ ▸ ✓ ✗ ⬢ ★ ·`) sized 13px in mono, color from role.
- No emoji in UI strings.

---

## 10. Accessibility

- All interactive elements are real `<button>` / `<a>` / `<select>`. No clickable `<div>` without a button role and keyboard handler.
- Text on `--bg-1` must be `--fg-2` or brighter. `--fg-3` is for labels and metadata only — never for body copy.
- `--fg-4` (`.dim`) is for disabled or deeply de-emphasized text only; never for anything the user has to read.
- Drawers and modals must trap focus, close on `Esc`, and have `aria-modal="true"`.
- Keyboard shortcuts (`1`/`2`/`3`/`4` for screen switching) must be discoverable in the Tweaks panel or a help overlay.

---

## 11. Data formatting

- Durations: `relTime` for "X ago" (`s`/`m`/`h`/`d` only). `durationFmt` for elapsed (`Ns`, `Nm SSs`, `Hh Mm`).
- Counts: `toLocaleString()` only for ≥10,000.
- Timestamps in mono, `HH:MM:SS` for "now-ish", `YYYY-MM-DD HH:MM` for absolute.
- Project / model names: as-is, mono, no truncation in tables (let the column widen). Truncate only inside `worker-beat` and feed rows where row height is fixed.
- Points: prefix `+` and color `--accent` when ≥1.

---

## 12. State conventions

- `busy` → accent stripe + accent-tinted border + pulsing dot.
- `idle` → muted text, no stripe, gray dot.
- `fail` → `--fail` color, no border change unless the failure blocks the row.
- `fresh` → 1.2s flash highlight, then resolve to default.

Don't invent additional states without adding them here first.

---

## 13. What you must not do

- Add a CSS framework (Tailwind, Bootstrap, etc.). The token system is the framework.
- Add UI libraries (MUI, Chakra, shadcn, etc.). Build from atoms.
- Hard-code colors, paddings, or font sizes outside the token grid.
- Introduce a build step without an explicit decision — see Migration Phase 6.
- Add a second accent color. The product has one accent; the role tints are separate.
- Use border-radius >4px, drop shadows, gradients (other than the page glow), or backdrop-blur.
- Animate anything on scroll.
- Introduce light mode in v1. The product is dark-only; light mode is a future, scoped project.

---

## 14. Adding a new screen

1. Define the data shape it consumes — write that down before you write JSX.
2. Add a route in `app.jsx`'s `screen` switch, and a `NavRail` entry.
3. Compose from existing panels first. Only build a new panel if no combination works.
4. Header is `.screen-h` (left: optional back btn + `<h1>`, right: `.meta`).
5. Wire keyboard shortcut if it's a top-level screen.
6. Update this doc if you introduced a new pattern that others should reuse.

---

## 15. Adding a new component

Checklist before merging:
- [ ] Uses tokens for every color, padding, and font.
- [ ] Renders correctly at all three densities.
- [ ] Renders correctly with each accent color.
- [ ] No new dependency.
- [ ] Mono for numbers/IDs, sans for prose.
- [ ] Hover/active states match `.btn` / `.proj-card` conventions.
- [ ] Keyboard reachable.
- [ ] Empty / loading / error states designed (don't ship just the happy path).
- [ ] Listed in section 6 of this doc if it's reusable.
