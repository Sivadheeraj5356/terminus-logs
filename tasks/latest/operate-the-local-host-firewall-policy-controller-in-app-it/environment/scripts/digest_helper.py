"""Reference digest helpers mirroring reconciliation-contract sha256 usage."""

from __future__ import annotations

import hashlib


def digest_bytes(data: bytes) -> str:
  return hashlib.sha256(data).hexdigest()
