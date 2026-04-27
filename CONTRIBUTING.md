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

Open http://127.0.0.1:18792.

## Tests

```bash
pytest tests/
```

## Versioning

loop-monitor independently versioned. The bounty event API contract is
shared with Loop core; bumping it requires coordination across both
repos.

## Reporting issues

- Use [GitHub Security Advisories](https://github.com/svv2014/loop-monitor/security/advisories/new)
  for vulnerabilities
- Public issues for bugs and features
