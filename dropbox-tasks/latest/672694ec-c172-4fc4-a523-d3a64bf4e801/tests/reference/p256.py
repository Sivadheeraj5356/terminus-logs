"""P-256 ECDSA verification via cryptography."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

# NIST P-256 order
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def parse_sec1_public_key(sec1: bytes) -> ec.EllipticCurvePublicKey:
    if len(sec1) != 65 or sec1[0] != 0x04:
        raise ValueError("invalid SEC1 point encoding")
    try:
        return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sec1)
    except ValueError as e:
        raise ValueError(f"invalid P-256 public key: {e}") from e


def verify_ecdsa_p256_sha256(public_sec1: bytes, message: bytes, r: bytes, s: bytes) -> bool:
    if len(r) != 32 or len(s) != 32:
        return False
    r_int = int.from_bytes(r, "big")
    s_int = int.from_bytes(s, "big")
    if r_int == 0 or s_int == 0 or r_int >= N or s_int >= N:
        return False
    try:
        key = parse_sec1_public_key(public_sec1)
    except ValueError:
        return False
    der = encode_dss_signature(r_int, s_int)
    try:
        key.verify(der, message, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


def sign_ecdsa_p256_sha256(
    private_key: ec.EllipticCurvePrivateKey, message: bytes
) -> tuple[bytes, bytes]:
    sig = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
    r_int, s_int = decode_dss_signature(sig)
    return r_int.to_bytes(32, "big"), s_int.to_bytes(32, "big")


# re-export for callers that need utils
__all__ = [
    "N",
    "parse_sec1_public_key",
    "verify_ecdsa_p256_sha256",
    "sign_ecdsa_p256_sha256",
    "utils",
]
