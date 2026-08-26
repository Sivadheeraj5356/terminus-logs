#!/usr/bin/env python3
"""Compare an emitted plan JSON to a golden plan file.

Usage: diff_plan.py <emitted.json> <golden.json>

Exit 0 if the two JSON documents are structurally equal.  The comparison
is ORDER-SENSITIVE on the actions array because the postmortem is
explicit that actions must be applied in the documented order (sysctl
before systemd drop-in before group before ulimit before permissions).

On mismatch, prints a unified diff on stderr with a short header showing
the missing / unexpected entries so the caller can tell whether the
submission drifted in ordering vs content.
"""
from __future__ import annotations

import difflib
import json
import sys


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: diff_plan.py <emitted.json> <golden.json>", file=sys.stderr)
        return 2
    emitted = load(argv[1])
    golden = load(argv[2])
    if emitted == golden:
        return 0
    e_lines = json.dumps(emitted, indent=2, sort_keys=False).splitlines(keepends=True)
    g_lines = json.dumps(golden, indent=2, sort_keys=False).splitlines(keepends=True)
    sys.stderr.write("PLAN MISMATCH:\n")
    sys.stderr.writelines(
        difflib.unified_diff(g_lines, e_lines, fromfile="golden", tofile="emitted")
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
