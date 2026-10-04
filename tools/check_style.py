#!/usr/bin/env python3
"""Reject em dashes, en dashes and emoji in tracked text files.

The project writes plain English without these characters (see CONTRIBUTING.md). Licence
texts are copied verbatim from their publishers and are skipped.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

BANNED = re.compile("[\u2013\u2014\u2600-\u27bf\ufe0f\U0001f000-\U0001faff]")
SKIP_PREFIXES = ("LICENSE",)
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".step", ".stp", ".stl", ".3mf", ".zip", ".xlsx", ".ico"}


def find_banned(text: str) -> list[tuple[int, int, str]]:
    """Return (line, column, character) for every banned character, 1-based."""
    hits = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in BANNED.finditer(line):
            hits.append((line_no, match.start() + 1, match.group()))
    return hits


def tracked_files(root: pathlib.Path) -> list[pathlib.Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
    return [root / name for name in out.decode().split("\0") if name]


def should_check(path: pathlib.Path) -> bool:
    return not path.name.startswith(SKIP_PREFIXES) and path.suffix.lower() not in BINARY_SUFFIXES


def main(argv: list[str]) -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    paths = [pathlib.Path(a) for a in argv] if argv else tracked_files(root)
    failures = 0
    for path in paths:
        if not should_check(path) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line, col, char in find_banned(text):
            print(f"{path}:{line}:{col}: banned character U+{ord(char):04X}")
            failures += 1
    if failures:
        print(f"{failures} banned character(s) found. Rewrite without dashes or emoji.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
