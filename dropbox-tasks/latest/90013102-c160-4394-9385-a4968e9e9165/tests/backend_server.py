"""Parse backend-capture JSON artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_capture(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"backend capture missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def capture_body_bytes(capture: dict[str, Any]) -> bytes:
    if capture.get("body_hex"):
        return bytes.fromhex(capture["body_hex"])
    return capture.get("body", "").encode("latin-1")


def capture_body_digest(capture: dict[str, Any]) -> str:
    return hashlib.sha256(capture_body_bytes(capture)).hexdigest()


def capture_headers_lower(capture: dict[str, Any]) -> dict[str, str]:
    headers = capture.get("headers", {})
    return {k.lower(): v for k, v in headers.items()}


def assert_capture_matches_expected(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    assert actual["method"] == expected["method"]
    assert actual["target"] == expected["target"]
    assert capture_body_bytes(actual) == capture_body_bytes(expected)
    for name, value in expected.get("headers", {}).items():
        assert actual["headers"].get(name) == value, (
            f"header {name}: expected {value!r}, got {actual['headers'].get(name)!r}"
        )
