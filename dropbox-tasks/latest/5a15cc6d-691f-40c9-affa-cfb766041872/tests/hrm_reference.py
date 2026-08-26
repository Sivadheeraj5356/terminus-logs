"""Independent HRM-1 reference used by the verifier harness."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
from pathlib import Path
from typing import Any

DEFAULT_ORDER = [1, 2, 3, 4, 5, 6]
OWS_SP = 1 << 0
OWS_HTAB = 1 << 1
OWS_NBSP = 1 << 2
DIGEST_COLON_STD = 0
DIGEST_BARE_STD = 1
DIGEST_COLON_URL = 2


def encode_profile(
    order: list[int] | None = None,
    ows_mask: int = OWS_SP | OWS_HTAB,
    digest_mode: int = DIGEST_COLON_STD,
) -> bytes:
    order = list(order or DEFAULT_ORDER)
    assert sorted(order) == list(range(1, 7))
    assert ows_mask & ~0x07 == 0
    assert digest_mode in (0, 1, 2)
    return (
        b"HRMP"
        + struct.pack("<HHB", 1, 0, 6)
        + bytes(order)
        + bytes([ows_mask & 0xFF, digest_mode & 0xFF])
    )


def load_keyring(path: Path) -> dict[str, bytes]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: base64.b64decode(v) for k, v in data["keys"].items()}


def canon_query(params: list[dict[str, str]]) -> str:
    items = sorted(((p["name"], p["value"]) for p in params), key=lambda x: (x[0], x[1]))
    return "&".join(f"{n}={v}" for n, v in items)


def _is_ows(ch: str, mask: int) -> bool:
    if ch == " " and mask & OWS_SP:
        return True
    if ch == "\t" and mask & OWS_HTAB:
        return True
    if ch == "\u00a0" and mask & OWS_NBSP:
        return True
    return False


def trim_ows(value: str, ows_mask: int = OWS_SP | OWS_HTAB) -> str:
    start = 0
    end = len(value)
    while start < end and _is_ows(value[start], ows_mask):
        start += 1
    while end > start and _is_ows(value[end - 1], ows_mask):
        end -= 1
    return value[start:end]


def canon_headers(
    headers: dict[str, str],
    covered: list[str],
    ows_mask: int = OWS_SP | OWS_HTAB,
) -> str:
    lower = {k.lower(): v for k, v in headers.items()}
    lines = []
    for name in covered:
        key = name.lower()
        if key not in lower:
            raise KeyError(name)
        val = trim_ows(lower[key], ows_mask)
        lines.append(f"{key}:{val}")
    return "\n".join(lines)


def content_digest(body: str, digest_mode: int = DIGEST_COLON_STD) -> str:
    dig = hashlib.sha256(body.encode("utf-8")).digest()
    if digest_mode == DIGEST_BARE_STD:
        return "sha-256=" + base64.b64encode(dig).decode("ascii")
    if digest_mode == DIGEST_COLON_URL:
        return "sha-256=:" + base64.urlsafe_b64encode(dig).decode("ascii").rstrip("=") + ":"
    return "sha-256=:" + base64.b64encode(dig).decode("ascii") + ":"


def canonical_request(
    env: dict[str, Any],
    *,
    ows_mask: int = OWS_SP | OWS_HTAB,
    digest_mode: int = DIGEST_COLON_STD,
) -> tuple[str, str]:
    cq = canon_query(env.get("query") or [])
    ch = canon_headers(env["headers"], env["covered"], ows_mask)
    cd = content_digest(env.get("body") or "", digest_mode)
    cr = "\n".join(
        [
            env["method"],
            env["path"],
            cq,
            ch,
            cd,
            str(env["created"]),
            str(env["expires"]),
        ]
    )
    return cr, cd


def mac_message(profile_bytes: bytes, canonical_request_bytes: bytes) -> bytes:
    """Profile-bound HMAC message: raw profile || 0x00 || canonical request."""
    return profile_bytes + b"\x00" + canonical_request_bytes


def expected_mac(
    env: dict[str, Any],
    keys: dict[str, bytes],
    *,
    ows_mask: int = OWS_SP | OWS_HTAB,
    digest_mode: int = DIGEST_COLON_STD,
    order: list[int] | None = None,
    profile_bytes: bytes | None = None,
) -> str:
    if profile_bytes is None:
        profile_bytes = encode_profile(
            order=order, ows_mask=ows_mask, digest_mode=digest_mode
        )
    cr, _ = canonical_request(env, ows_mask=ows_mask, digest_mode=digest_mode)
    digest = hmac.new(
        keys[env["kid"]],
        mac_message(profile_bytes, cr.encode("utf-8")),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def expected_ok_line(
    env: dict[str, Any],
    keys: dict[str, bytes],
    *,
    ows_mask: int = OWS_SP | OWS_HTAB,
    digest_mode: int = DIGEST_COLON_STD,
) -> str:
    _cr, cd = canonical_request(env, ows_mask=ows_mask, digest_mode=digest_mode)
    return f"ok kid={env['kid']} digest={cd}\n"


def load_envelope(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
