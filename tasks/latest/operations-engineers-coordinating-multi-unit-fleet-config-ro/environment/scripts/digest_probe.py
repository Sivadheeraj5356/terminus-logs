# Operator digest probe — SHA-256 helpers for fleet seal and slot witnesses.
import hashlib


def hex_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
