"""Merkle tree construction from record-hash leaves."""

from hash_utils import sha256_hex


def build_merkle_root(leaves):
    if not leaves:
        return sha256_hex("")
    current = list(leaves)
    while len(current) > 1:
        next_level = []
        for index in range(0, len(current), 2):
            left = current[index]
            right = current[index + 1] if index + 1 < len(current) else current[index]
            next_level.append(sha256_hex(f"{left}:{right}"))
        current = next_level
    return current[0]
