"""Small hashlib helper kept for stamp tooling parity with the matrix contract."""

import hashlib


def hex_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
