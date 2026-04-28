#!/usr/bin/env bash
# Bump VERSION, add a CHANGELOG entry stub, commit, and tag for release.
#
# Usage: scripts/release.sh <new-version>
# Example: scripts/release.sh 0.2.0
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$REPO_ROOT/VERSION"
CHANGELOG="$REPO_ROOT/CHANGELOG.md"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <new-version>" >&2
  exit 1
fi

NEW_VERSION="$1"

# Validate semver-ish format (major.minor.patch)
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: version must be in X.Y.Z format, got: $NEW_VERSION" >&2
  exit 1
fi

OLD_VERSION="$(cat "$VERSION_FILE")"
TODAY="$(date +%Y-%m-%d)"

echo "Releasing $OLD_VERSION → $NEW_VERSION"

# Update VERSION file
echo "$NEW_VERSION" > "$VERSION_FILE"

# Insert CHANGELOG entry after the [Unreleased] header
ENTRY="## [$NEW_VERSION] - $TODAY\n\n### Changed\n\n- Release $NEW_VERSION\n"
sed -i.bak "s/^## \[Unreleased\]/## [Unreleased]\n\n${ENTRY}/" "$CHANGELOG"
rm -f "$CHANGELOG.bak"

# Commit and tag
git -C "$REPO_ROOT" add VERSION CHANGELOG.md
git -C "$REPO_ROOT" commit -m "release: v$NEW_VERSION (bump VERSION + CHANGELOG entry)"
git -C "$REPO_ROOT" tag "v$NEW_VERSION"

echo "Done. Push with:"
echo "  git push origin main && git push origin v$NEW_VERSION"
