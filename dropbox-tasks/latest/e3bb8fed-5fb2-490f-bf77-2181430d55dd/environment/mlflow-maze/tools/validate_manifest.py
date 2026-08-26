#!/usr/bin/env python3
"""Validate one recovered maze manifest against the published JSON Schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fastjsonschema


def main() -> int:
    """Return success only when the named manifest satisfies the named schema."""
    if len(sys.argv) != 3:
        return 2
    try:
        schema = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        fastjsonschema.compile(schema)(manifest)
    except (OSError, ValueError, fastjsonschema.JsonSchemaException):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
