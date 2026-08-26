#!/usr/bin/env bash
set -euo pipefail

cd /app/repo

EFFECT_UPSTREAM_COMMIT="3e59443be029e99d2b457bb43f682feb5ebcd2e0"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

git clone https://github.com/Effect-TS/effect.git "$WORKDIR/effect" >/dev/null 2>&1
git -C "$WORKDIR/effect" checkout "$EFFECT_UPSTREAM_COMMIT" >/dev/null 2>&1

for name in printer printer-ansi; do
    src="$WORKDIR/effect/packages/$name"
    dest="/app/repo/packages/$name"

    if [ ! -d "$src" ]; then
        echo "Upstream package missing at pinned commit: $src" >&2
        exit 1
    fi

    rm -rf "$dest"
    cp -a "$src" "$dest"
done

python3 <<'PY'
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path("/app/repo")
PACKAGES = REPO_ROOT / "packages"

for name in ("printer", "printer-ansi"):
    pkg_dir = PACKAGES / name
    if not pkg_dir.is_dir():
        raise SystemExit(f"Package restoration failed: {pkg_dir}")

    pkg_json = pkg_dir / "package.json"
    if not pkg_json.is_file():
        raise SystemExit(f"Missing package manifest: {pkg_json}")

printer_ansi_manifest = PACKAGES / "printer-ansi" / "package.json"

manifest = json.loads(printer_ansi_manifest.read_text())

deps = manifest.setdefault("dependencies", {})
deps["@effect/printer"] = "workspace:^"

printer_ansi_manifest.write_text(
    json.dumps(manifest, indent=2) + "\n"
)

lockfile = REPO_ROOT / "pnpm-lock.yaml"

text = lockfile.read_text()

pattern = re.compile(
    r"(packages/printer-ansi:\n"
    r"    dependencies:\n"
    r"      '@effect/printer':\n"
    r"        specifier: )([^\n]+)"
)

patched, count = pattern.subn(
    r"\g<1>workspace:^",
    text,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Unable to locate printer-ansi dependency entry in pnpm-lock.yaml."
    )

lockfile.write_text(patched)
PY