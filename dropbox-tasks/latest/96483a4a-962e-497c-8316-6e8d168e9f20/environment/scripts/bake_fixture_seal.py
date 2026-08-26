#!/usr/bin/env python3
"""Bake read-only fixture seal for verifier integrity checks only."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/app/environment")
SEAL = Path("/opt/task-seal/environment")

if SEAL.exists():
    shutil.rmtree(SEAL.parent)
shutil.copytree(ROOT, SEAL)

manifest: dict[str, str] = {}
include_dirs = ["fixtures/maps", "fixtures/puzzles", "fixtures/training", "docs", "schemas"]
for rel_dir in include_dirs:
    base = SEAL / rel_dir
    if not base.is_dir():
        continue
    for path in sorted(base.rglob("*")):
        if path.is_file():
            rel = path.relative_to(SEAL).as_posix()
            manifest[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

manifest_path = Path("/opt/task-seal/manifest.json")
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
subprocess.run(["chmod", "-R", "a-w", "/opt/task-seal"], check=True)
