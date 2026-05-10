# Contributing to loop-monitor

loop-monitor is the companion dashboard for [Loop](https://github.com/svv2014/loop).
External contributions welcome.

## Quick rules

- One concern per PR — don't bundle unrelated changes
- Branch naming: `fix/issue-N-short-slug` or `feat/issue-N-short-slug`
- PR body must contain `Closes #N`
- All CI checks must pass
- Approval from a [CODEOWNERS](.github/CODEOWNERS) reviewer is
  required before merge
- Don't break the **bounty event API v1.0** contract without bumping
  the API version (see CHANGELOG.md and the spec in Loop core)

## Local dev

```bash
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 18792 --reload
```

## Code quality

This repo uses [ruff](https://docs.astral.sh/ruff/) for linting/formatting and
[pyright](https://github.com/microsoft/pyright) for type checking.

**One-time setup** — install the pre-commit hooks so checks run automatically before every commit:

```bash
pip install pre-commit
pre-commit install
```

**Run checks manually:**

```bash
# Lint + format check
ruff check .

# Type check (server only)
pyright server/

# Run all pre-commit hooks against every file
pre-commit run --all-files
```

CI runs `ruff check .` and `pyright server/` on every PR and push to `main`.

Open http://127.0.0.1:18792.

## Tests

```bash
pytest tests/
```

## Frontend (`web/`)

The dashboard UI is being migrated from vanilla JS (`static/`) to a React + TypeScript app under `web/`. Until phase 5 of the migration, both coexist.

**Required reading before opening a frontend PR:**

- [`design/MIGRATION.md`](design/MIGRATION.md) — phased migration plan
- [`design/DESIGN_STANDARDS.md`](design/DESIGN_STANDARDS.md) — design tokens + component rules (binding)
- [`design/new-design/README.md`](design/new-design/README.md) — frozen reference prototype
- [`docs/adr/0001-frontend-stack.md`](docs/adr/0001-frontend-stack.md) — Vite + React + TS
- [`docs/adr/0002-visual-regression.md`](docs/adr/0002-visual-regression.md) — visual-diff CI gate

**Local dev** (after `web/` lands in phase 1):

```bash
cd web
npm ci
npm run dev   # Vite dev server, proxies /api/* to the backend
```

PRs touching the UI must pass the visual-diff suite (`pytest tests/visual/`) and include a screenshot in the description.

## Versioning

loop-monitor is independently versioned from Loop core using
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Use `scripts/release.sh patch|minor|major` to cut a release — it bumps
`VERSION`, commits, tags, pushes, and creates a GitHub Release with the
CHANGELOG excerpt automatically.

### Pre-1.0 policy (current)

While the major version is **0**, a MINOR bump (`0.X.0`) may introduce
breaking changes to loop-monitor's own HTTP API or database schema.
Every such change **must**:

1. Include the word **BREAKING** in the CHANGELOG entry for that version.
2. Include a migration recipe explaining how existing deployments should
   update (SQL `ALTER TABLE` statements, config key renames, etc.).

Patch bumps (`0.X.Y`) must remain backwards-compatible.

### Post-1.0 policy

Once `1.0.0` ships, strict semver applies:

- **MAJOR** — any backwards-incompatible change to a public interface.
- **MINOR** — new backwards-compatible functionality.
- **PATCH** — backwards-compatible bug fixes only.

### Bounty event API contract

The bounty event API (`/api/report`, `/api/verdict`) is a **shared
contract** between loop-monitor and Loop core. Its version (`api: "1.x"`)
is baked into every payload.

- Changing the API contract requires a coordinated bump in **both** repos.
- Additive-only changes (new optional fields) may be shipped as a MINOR
  bump without breaking Loop core clients.
- Any removal or rename of an existing field is a **major API version**
  bump and requires updating the spec in Loop core first.

## Reporting issues

- Use [GitHub Security Advisories](https://github.com/svv2014/loop-monitor/security/advisories/new)
  for vulnerabilities
- Public issues for bugs and features
