#!/usr/bin/env python3
"""Drift check for vendored Butler Framework memory code.

Compares the three mechanical copies exactly (after the single import
rewrite) and compares the extracted slices against the recorded upstream
SHA-256 baselines. Any mismatch means the upstream changed and a re-sync
is required (see VENDORED.md).

Usage:
    python scripts/check-vendored.py --upstream /path/to/ai-butler-framework
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
VENDORED = PKG / "src" / "ai_butler_memory_mcp" / "vendored"


def _identity(text: str) -> str:
    return text


def _database_rewrite(text: str) -> str:
    return text.replace("from .config import", "from ..config import")


# Mechanical copies: (vendored name, upstream relative path, transform).
# transform=None marks the config prefix slice (first N lines of vendored).
MECHANICAL = [
    ("models.py", "src/ai_butler_runtime/persistence/models.py", _identity),
    (
        "database.py",
        "src/ai_butler_runtime/persistence/database.py",
        _database_rewrite,
    ),
    ("config.py", "src/ai_butler_runtime/config.py", None),
]

# Extracted slices: name, upstream relative path, and (start, end, baseline)
# per 1-based inclusive line range.
EXTRACTED = [
    {
        "name": "memory_policy.py",
        "rel": "src/ai_butler_runtime/memory_policy.py",
        "slices": [(48, 97, "55559805309aaf4b43686dfbbb24d7815208dd6f6a8997d4f8b1e6f92b90bda5"), (367, 423, "ef195b3ffc014620de35ad5b769039d9b71974a30be1ca18314a294ac7465cdc")],
    },
    {
        "name": "memory_service.py",
        "rel": "src/ai_butler_runtime/persistence/services.py",
        "slices": [(222, 292, "a012c3d761fba757533650f45d879ad5d3c2c8f30108f4b7a10df2ba5903a00d"), (3374, 3730, "30a02a6193877b23d1a2d9e21674d4907f11647258e39500f4afac652a02a11d")],
    },
    {
        "name": "layered_memory.py",
        "rel": "src/ai_butler_runtime/persistence/memory_services.py",
        "slices": [(75, 617, "a4eb8755d76394e1304041c1eb10487562775b26bf476d53af7241a6d8cfe6cf")],
    },
]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slice_text(lines: list[str], start: int, end: int) -> str:
    return "".join(line + "\n" for line in lines[start - 1 : end])


def check(upstream: Path) -> list[str]:
    problems: list[str] = []

    for name, rel, transform in MECHANICAL:
        upstream_file = upstream / rel
        vendored_file = VENDORED / name
        if not upstream_file.is_file():
            problems.append(f"upstream missing: {rel}")
            continue
        if not vendored_file.is_file():
            problems.append(f"vendored missing: {name}")
            continue
        if transform is None:
            line_count = len(vendored_file.read_text().splitlines())
            expected = "\n".join(
                upstream_file.read_text().splitlines()[:line_count]
            ) + "\n"
            ok = expected == vendored_file.read_text()
        else:
            ok = transform(vendored_file.read_text()) == upstream_file.read_text()
        if not ok:
            problems.append(f"DRIFT: {name} differs from upstream {rel}")

    for entry in EXTRACTED:
        upstream_file = upstream / entry["rel"]
        if not upstream_file.is_file():
            problems.append(f"upstream missing: {entry['rel']}")
            continue
        lines = upstream_file.read_text().splitlines()
        for start, end, baseline in entry["slices"]:
            current = sha256(slice_text(lines, start, end))
            if baseline.startswith("tbd"):
                print(f"baseline for {entry['name']} slice {start}-{end}: {current}")
            elif current != baseline:
                problems.append(
                    f"DRIFT: {entry['name']} slice {start}-{end} of "
                    f"{entry['rel']} changed"
                )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Check vendored drift")
    parser.add_argument("--upstream", required=True, type=Path)
    args = parser.parse_args()
    problems = check(args.upstream)
    if problems:
        print("VENDORED DRIFT DETECTED:", file=sys.stderr)
        for problem in problems:
            print(" -", problem, file=sys.stderr)
        return 1
    print("vendored code matches the recorded upstream baselines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
