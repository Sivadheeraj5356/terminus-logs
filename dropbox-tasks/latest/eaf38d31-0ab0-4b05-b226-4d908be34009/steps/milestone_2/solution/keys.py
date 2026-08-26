"""Ed25519 signing-key management and manifest signature operations."""

import base64
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate_keypair(key_dir: str) -> tuple[str, str]:
    """Generate an Ed25519 keypair and write PEM files. Returns (priv, pub) paths."""
    d = Path(key_dir)
    d.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()

    priv_path = d / "ed25519_private.pem"
    pub_path = d / "ed25519_public.pem"

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path.write_bytes(priv_bytes)
    pub_path.write_bytes(pub_bytes)
    return str(priv_path), str(pub_path)


def load_private_key(priv_path: str) -> Ed25519PrivateKey:
    data = Path(priv_path).read_bytes()
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("not an Ed25519 private key")
    return key


def load_public_key(pub_path: str) -> Ed25519PublicKey:
    data = Path(pub_path).read_bytes()
    key = serialization.load_pem_public_key(data)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("not an Ed25519 public key")
    return key


def sign_digest(priv_path: str, digest_hex: str) -> str:
    """Sign the bytes of the hex digest string; return base64 signature."""
    key = load_private_key(priv_path)
    sig = key.sign(digest_hex.encode("ascii"))
    return base64.b64encode(sig).decode("ascii")


def verify_digest(pub_path: str, digest_hex: str, signature_b64: str) -> bool:
    key = load_public_key(pub_path)
    try:
        key.verify(base64.b64decode(signature_b64), digest_hex.encode("ascii"))
        return True
    except (InvalidSignature, ValueError):
        return False
