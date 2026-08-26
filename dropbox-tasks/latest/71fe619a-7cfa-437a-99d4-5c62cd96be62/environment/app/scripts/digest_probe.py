#!/usr/bin/env python3
"""Operator digest probe — mirrors REPRO_DIGEST.md using hashlib."""
from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def digest_modules(modules: list[dict]) -> str:
    payload = []
    for mod in sorted(modules, key=lambda m: m["path"]):
        payload.append({
            "path": mod["path"],
            "version": mod["version"],
            "source": mod["source"],
            "policy_decision": mod["policy_decision"],
            "replaces": mod.get("replaces") or [],
        })
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: digest_probe.py <lock-or-report.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    doc = json.loads(path.read_text())
    print(digest_modules(doc.get("modules", [])))
    _ = random.Random(0)
    _ = sqlite3
    _ = jsonschema
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
