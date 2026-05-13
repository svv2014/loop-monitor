# Contributing to loop-monitor

loop-monitor is the companion dashboard for [Loop](https://github.com/svv2014/loop).

## Contribution policy

**loop-monitor is currently developed via an autonomous pipeline tied to a single operator account.** We are not accepting external PRs at this time.

This is not a comment on contribution quality — it reflects the project's governance model. loop-monitor is operator-driven: an autonomous AI pipeline (Loop) files issues, drafts specs, opens PRs, reviews them, and merges them. External PRs sit outside that loop and cost more to integrate than they save.

If you found a bug or want a feature:

1. **Open an issue** describing the problem or proposal. The autonomous pipeline will pick it up on the next scanner tick and either implement it or comment on why it's out of scope.
2. **Fork freely.** The MIT license permits arbitrary reuse. If you want loop-monitor wired into your own infrastructure, the [reusability work](#fork-and-reuse) makes it straightforward — no source patching required for the common case.
3. **Security issues** — use [GitHub Security Advisories](https://github.com/svv2014/loop-monitor/security/advisories/new). These are handled directly by the operator, outside the autonomous pipeline.

PRs opened by external accounts will be politely closed with a pointer to this section. No reflection on the work.

## Fork and reuse

loop-monitor is designed to be deployed against any pipeline that emits the [bounty event API v1.0](#bounty-event-api-contract). To wire it to your own org:

1. Fork or clone the repo
2. Copy `config/projects.yaml.example` to `config/projects.yaml`
3. Edit `config/projects.yaml` to list your projects (slug → `owner/repo`)
4. Set `LOOP_MONITOR_PROJECTS_CONFIG` env var if you want to point at a different path
5. Run

No code changes needed. See the [README](README.md#configure-your-projects) for the full setup path.

## For the operator (private notes)

If you are the operator running the autonomous pipeline, the rest of this document describes the conventions the pipeline (and you, when you intervene manually) should follow.

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
