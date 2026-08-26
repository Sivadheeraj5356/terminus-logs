#!/usr/bin/env python3
"""Ensure the ML model deployment registry is running for audit verification."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request

REGISTRY_URL = "http://127.0.0.1:8080/v1/models/fraud_guard_prod/deployment"


def registry_ready() -> bool:
    try:
        with urllib.request.urlopen(REGISTRY_URL, timeout=1) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main() -> int:
    if registry_ready():
        return 0
    subprocess.Popen(
        [sys.executable, "/app/registry/app.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        time.sleep(0.5)
        if registry_ready():
            return 0
    print("ML deployment registry failed to start", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
