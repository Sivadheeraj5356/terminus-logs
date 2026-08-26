"""SHA-256 hex helpers shared with verifier-side digest checks."""


def sha256_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def journal_tag(digest_sha: str, profile: str, bundle: str) -> str:
    material = f"{digest_sha}|{profile}|{bundle}".encode()
    return sha256_hex(material)[:8]
