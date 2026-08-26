"""Independent HMAC-SHA256 signing and canonical message construction."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Iterable

MASTER_SEED = b"tb3-request-signature-proxy-canonicalization-v1"
BODY_LIMIT = 1048576

HOP_BY_HOP = {
    "Connection",
    "Keep-Alive",
    "Proxy-Authenticate",
    "Proxy-Authorization",
    "Te",
    "Trailers",
    "Transfer-Encoding",
    "Upgrade",
}

CURRENT_SINGLETON = {
    "Host",
    "X-Sig-Profile",
    "X-Sig-Tenant",
    "X-Sig-Key-Id",
    "X-Sig-Nonce",
    "Content-Type",
}
CURRENT_JOINABLE = {"Accept", "X-Test-List"}
CURRENT_ORDER_PRESERVING = {"X-Order-Field"}
CURRENT_SIGNED = {"Host", "Content-Type", "Accept", "X-Test-List", "X-Order-Field"}

LEGACY_SIGNED = {"Host", "Content-Type"}


@dataclass
class HeaderField:
    name: str
    value: str


@dataclass
class SemanticRequest:
    request_id: str
    profile_id: str
    profile_epoch: int
    signature_version: int
    tenant: str
    key_id: str
    key_epoch: int
    method: str
    authority: str
    wire_target: str
    canonical_target: str
    canonical_headers: list[HeaderField]
    entity_body: bytes
    request_nonce: str
    entity_body_sha256: str = field(init=False)
    entity_body_length: int = field(init=False)

    def __post_init__(self) -> None:
        self.entity_body_sha256 = body_digest(self.entity_body)
        self.entity_body_length = len(self.entity_body)


def derive_secret(test_name: str, label: str = "hmac") -> bytes:
    return hmac.new(MASTER_SEED, f"{test_name}:{label}".encode(), hashlib.sha256).digest()


def derive_hex(test_name: str, label: str, nbytes: int = 32) -> str:
    out = b""
    counter = 0
    while len(out) < nbytes:
        out += hmac.new(
            MASTER_SEED,
            f"{test_name}:{label}:{counter}".encode(),
            hashlib.sha256,
        ).digest()
        counter += 1
    return out[:nbytes].hex()


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_message_digest(message: str) -> str:
    return hashlib.sha256(message.encode()).hexdigest()


def _canonical_mime(name: str) -> str:
    parts = name.split("-")
    return "-".join(part[:1].upper() + part[1:].lower() for part in parts if part != "")


def _lower_name(name: str) -> str:
    return _canonical_mime(name).lower()


def _connection_tokens(headers: dict[str, list[str]]) -> set[str]:
    nominated: set[str] = set()
    for value in headers.get("Connection", []):
        for tok in value.split(","):
            tok = tok.strip().lower()
            if tok:
                nominated.add(tok)
    return nominated


def apply_header_policy(
    headers: dict[str, list[str]],
    header_order: Iterable[str],
    *,
    signature_version: int,
    pre_verify: bool = False,
) -> list[HeaderField]:
    """Apply documented header policy; default path matches backend forwarding."""
    singleton = CURRENT_SINGLETON
    joinable = CURRENT_JOINABLE
    order_preserving = CURRENT_ORDER_PRESERVING
    nominated = _connection_tokens(headers) if not pre_verify else set()

    filtered: dict[str, list[str]] = {}
    order: list[str] = []
    seen: set[str] = set()
    for name in header_order:
        canon = _canonical_mime(name)
        if canon in seen:
            continue
        seen.add(canon)
        if pre_verify:
            if canon in HOP_BY_HOP and canon != "Connection":
                continue
        else:
            ln = _lower_name(name)
            if canon in HOP_BY_HOP or ln in nominated:
                continue
        vals = headers.get(name, headers.get(canon, []))
        if not vals:
            continue
        order.append(canon)
        filtered[canon] = list(vals)

    out: list[HeaderField] = []
    for name in order:
        vals = filtered[name]
        canon = _canonical_mime(name)
        ln = _lower_name(name)

        if canon in singleton:
            if len(vals) > 1:
                raise ValueError(f"duplicate singleton header {name}")
            if vals:
                out.append(HeaderField(ln, vals[0].strip()))
            continue

        if canon in joinable:
            parts = [v.strip() for v in vals]
            out.append(HeaderField(ln, ", ".join(parts)))
            continue

        if canon in order_preserving:
            for v in vals:
                out.append(HeaderField(ln, v.strip()))
            continue

        if len(vals) > 1:
            raise ValueError(f"duplicate header {name}")
        if vals:
            out.append(HeaderField(ln, vals[0].strip()))

    return out


def filter_signed_headers(
    fields: list[HeaderField], *, signature_version: int
) -> list[HeaderField]:
    signed = LEGACY_SIGNED if signature_version == 1 else CURRENT_SIGNED
    out: list[HeaderField] = []
    for hdr in fields:
        canon = _canonical_mime(hdr.name)
        if canon in signed or hdr.name in signed:
            out.append(hdr)
    return out


def build_v2_message(sem: SemanticRequest) -> str:
    lines = [
        "LOCAL-SIG-V2",
        f"profile:{sem.profile_id}@{sem.profile_epoch}",
        f"key:{sem.tenant}/{sem.key_id}@{sem.key_epoch}",
        f"method:{sem.method}",
        f"authority:{sem.authority}",
        f"target:{sem.canonical_target}",
        f"headers:{len(sem.canonical_headers)}",
    ]
    for header in sem.canonical_headers:
        lines.append(f"{header.name}:{header.value}")
    lines.extend(
        [
            f"body-sha256:{sem.entity_body_sha256}",
            f"body-length:{sem.entity_body_length}",
            f"nonce:{sem.request_nonce}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_v1_message(sem: SemanticRequest) -> str:
    lines = [
        "LOCAL-SIG-V1",
        f"tenant:{sem.tenant}",
        f"key:{sem.key_id}@{sem.key_epoch}",
        f"profile:{sem.profile_id}",
        f"{sem.method} {sem.canonical_target}",
        f"host:{sem.authority}",
    ]
    for header in sem.canonical_headers:
        lines.append(f"h:{header.name}={header.value}")
    lines.extend(
        [
            f"body:{sem.entity_body_sha256}:{sem.entity_body_length}",
            f"nonce:{sem.request_nonce}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_canonical_message(sem: SemanticRequest) -> str:
    if sem.signature_version == 1:
        return build_v1_message(sem)
    if sem.signature_version == 2:
        return build_v2_message(sem)
    raise ValueError(f"unsupported signature version {sem.signature_version}")


def sign_semantic(sem: SemanticRequest, secret: bytes) -> str:
    message = build_canonical_message(sem)
    digest = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
    return f"v{sem.signature_version} {digest}"


def expected_canonical_digest(sem: SemanticRequest) -> str:
    return canonical_message_digest(build_canonical_message(sem))
