"""Reference digest helper."""
import hashlib

def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()
