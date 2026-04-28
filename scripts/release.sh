#!/usr/bin/env bash
# release.sh — bump VERSION, commit, tag, push, create GitHub Release.
# Usage: release.sh patch|minor|major
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="${REPO_ROOT}/VERSION"
CHANGELOG_FILE="${REPO_ROOT}/CHANGELOG.md"

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
BUMP="${1:?Usage: release.sh patch|minor|major}"

if ! [[ "$BUMP" =~ ^(patch|minor|major)$ ]]; then
    echo "error: argument must be one of: patch, minor, major" >&2
    exit 1
fi

if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
    echo "error: working tree is dirty — commit or stash changes first" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Compute new version
# ---------------------------------------------------------------------------
CURRENT="$(tr -d '[:space:]' < "$VERSION_FILE")"
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

case "$BUMP" in
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    patch) PATCH=$((PATCH + 1)) ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
TAG="v${NEW_VERSION}"

echo "Bumping ${CURRENT} → ${NEW_VERSION} (${BUMP})"

# ---------------------------------------------------------------------------
# Write new VERSION
# ---------------------------------------------------------------------------
printf '%s\n' "$NEW_VERSION" > "$VERSION_FILE"

# ---------------------------------------------------------------------------
# Extract CHANGELOG entry for the new version (if present)
# ---------------------------------------------------------------------------
RELEASE_NOTES="$(python3 - "$NEW_VERSION" "$CHANGELOG_FILE" <<'PYEOF'
import re, sys

tag = sys.argv[1]

with open(sys.argv[2]) as f:
    text = f.read()

pattern = rf'## \[{re.escape(tag)}\][^\n]*\n(.*?)(?=\n## |\Z)'
m = re.search(pattern, text, re.DOTALL)
if m:
    print(m.group(1).strip())
PYEOF
)" || true

if [[ -z "$RELEASE_NOTES" ]]; then
    RELEASE_NOTES="Release ${TAG}"
fi

# ---------------------------------------------------------------------------
# Commit, tag, push
# ---------------------------------------------------------------------------
git -C "$REPO_ROOT" add "$VERSION_FILE"
git -C "$REPO_ROOT" commit -m "release: v${NEW_VERSION}"
git -C "$REPO_ROOT" tag "$TAG"
git -C "$REPO_ROOT" push origin HEAD
git -C "$REPO_ROOT" push origin "$TAG"

# ---------------------------------------------------------------------------
# Create GitHub Release
# ---------------------------------------------------------------------------
gh release create "$TAG" \
    --repo "$(gh repo view --json nameWithOwner -q .nameWithOwner)" \
    --title "$TAG" \
    --notes "$RELEASE_NOTES"

echo "Released ${TAG}"
