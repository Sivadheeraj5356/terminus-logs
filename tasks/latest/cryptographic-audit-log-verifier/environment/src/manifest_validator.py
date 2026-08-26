"""Manifest signature verification."""

from hash_utils import is_valid_sha256, sha256_hex


def verify_manifest_signature(segment_roots, stored_signature):
    if not is_valid_sha256(stored_signature):
        return False, "malformed_hash"
    concatenated = "\n".join(segment_roots)
    expected = sha256_hex(concatenated)
    if expected == stored_signature:
        return True, None
    return False, "bad_manifest_signature"
