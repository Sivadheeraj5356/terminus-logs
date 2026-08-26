"""Desk digest helpers used by operators and verifier math."""

from __future__ import annotations

import hashlib
import tarfile
import urllib.request
from pathlib import Path


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def tar_member_names(path: str | Path) -> list[str]:
    with tarfile.open(path, "r") as tf:
        return list(tf.getnames())


def fetch_bytes(url: str, timeout: float = 5.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()
