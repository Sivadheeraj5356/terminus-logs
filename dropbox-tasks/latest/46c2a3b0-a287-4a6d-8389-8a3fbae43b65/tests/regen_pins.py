#!/usr/bin/env python3
"""Regenerate golden fixtures and input SHA-256 pins."""
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def pins_for_tar(fixtures: Path) -> dict[str, str]:
    env = fixtures.parent.parent / "environment"
    data = env / "data"
    spec = env / "spec"
    pins = {
        "backup_config.json": sha256_file(data / "backup_config.json"),
        "spec/output_formats.json": sha256_file(spec / "output_formats.json"),
        "spec/SPEC.md": sha256_file(spec / "SPEC.md"),
    }
    for path in sorted((data / "src").rglob("*")):
        if path.is_file():
            pins[f"src/{path.relative_to(data / 'src').as_posix()}"] = sha256_file(path)
    return pins


def pins_for_elf(fixtures: Path) -> dict[str, str]:
    return {"binary.elf": sha256_file(fixtures.parent.parent / "environment" / "data" / "binary.elf")}


def pins_for_grid(fixtures: Path) -> dict[str, str]:
    data = fixtures.parent.parent / "environment" / "data"
    return {
        "map.json": sha256_file(data / "map.json"),
        "requests.json": sha256_file(data / "requests.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=("tar", "elf", "grid"))
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()

    if args.task == "tar":
        pins = pins_for_tar(args.fixtures)
    elif args.task == "elf":
        pins = pins_for_elf(args.fixtures)
    else:
        pins = pins_for_grid(args.fixtures)

    out = args.fixtures / "_input_sha256.json"
    out.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
