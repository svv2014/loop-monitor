#!/usr/bin/env python3
"""Fail if any operator-specific project/identity name appears in tracked files.

The list of names to forbid lives in scripts/.operator-names.local.txt
(gitignored). One name per line; blank lines and `#` comments are ignored.
The committed default list is empty so the check is a no-op until an operator
populates it locally / in CI secrets.

CHANGELOG.md is exempt (historical references are allowed to stand).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES_FILE = ROOT / "scripts" / ".operator-names.local.txt"
EXEMPT = {"CHANGELOG.md"}


def load_names() -> list[str]:
    if not NAMES_FILE.exists():
        return []
    out: list[str] = []
    for line in NAMES_FILE.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def tracked_files() -> list[str]:
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [p for p in res.stdout.splitlines() if p and p not in EXEMPT]


def main() -> int:
    names = load_names()
    if not names:
        print("check-no-operator-leaks: no names configured (scripts/.operator-names.local.txt empty or missing) — skipping")
        return 0

    files = tracked_files()
    hits: list[tuple[str, str, int, str]] = []
    for path in files:
        abs_path = ROOT / path
        if not abs_path.is_file():
            continue
        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            for name in names:
                if name in line:
                    hits.append((path, name, lineno, line.strip()))

    if hits:
        print("check-no-operator-leaks: FAIL — operator-specific names found in tracked files:", file=sys.stderr)
        for path, name, lineno, snippet in hits:
            print(f"  {path}:{lineno}  [{name}]  {snippet[:120]}", file=sys.stderr)
        return 1

    print(f"check-no-operator-leaks: OK ({len(names)} name(s) checked across {len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
