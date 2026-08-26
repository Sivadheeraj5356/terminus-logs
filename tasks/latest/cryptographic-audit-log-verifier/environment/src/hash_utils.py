"""Hash format checks and record-hash recomputation."""

import hashlib


def is_valid_sha256(value):
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    normalized = value.lower()
    return all(c in "0123456789abcdef" for c in normalized)


def compute_record_hash(event_id, timestamp, payload, previous_hash):
    serialized = f"{event_id}:{timestamp}:{payload}:{previous_hash}"
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
