"""Build raw HTTP/1.1 requests and seeded semantic cases."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from signature_factory import (
    BODY_LIMIT,
    SemanticRequest,
    apply_header_policy,
    derive_hex,
    filter_signed_headers,
    sign_semantic,
)

__all__ = ["derive_hex"]

MASTER_SEED = b"tb3-request-signature-proxy-canonicalization-v1"


@dataclass
class ProfileSpec:
    profile_id: str
    epoch: int
    signature_version: int
    preserve_legacy_query: bool = False
    uppercase_percent: bool = False
    remove_dot_segments: bool = False


CURRENT_PROFILE = ProfileSpec(
    "current-2026", 1, 2, False, True, True
)
LEGACY_PROFILE = ProfileSpec("legacy-2024", 1, 1, True, False, False)
TRANSITION_PROFILE = ProfileSpec("transition-2025", 1, 2, False, True, True)
CACHE_PROFILE_B = ProfileSpec("cache-profile-b", 2, 2, False, True, True)


def seeded_bytes(test_name: str, *labels: str, size: int = 32) -> bytes:
    msg = test_name + "|" + "|".join(labels)
    out = b""
    counter = 0
    while len(out) < size:
        out += hmac.new(MASTER_SEED, f"{msg}:{counter}".encode(), hashlib.sha256).digest()
        counter += 1
    return out[:size]


def seeded_choice(test_name: str, label: str, choices: list[str]) -> str:
    idx = seeded_bytes(test_name, label, size=1)[0] % len(choices)
    return choices[idx]


def seeded_nonce(test_name: str, label: str = "nonce") -> str:
    return derive_hex(test_name, label, 8)


def seeded_request_id(test_name: str, label: str = "req") -> str:
    return f"req-{derive_hex(test_name, label, 6)}"


def normalize_method(method: str) -> str:
    if not method:
        raise ValueError("empty method")
    if not re.fullmatch(r"[\x21-\x7E]+", method):
        raise ValueError("invalid method character")
    return method.upper()


def _is_hex(ch: str) -> bool:
    return ch.isdigit() or ("A" <= ch.upper() <= "F")


def _decode_path_segments(path: str, uppercase: bool) -> str:
    out: list[str] = []
    i = 0
    while i < len(path):
        if path[i] != "%":
            out.append(path[i])
            i += 1
            continue
        if i + 2 >= len(path):
            raise ValueError("malformed percent encoding")
        hx = path[i + 1 : i + 3]
        if not _is_hex(hx[0]) or not _is_hex(hx[1]):
            raise ValueError("malformed percent encoding")
        if uppercase:
            hx = hx.upper()
        out.append("%")
        out.append(hx)
        i += 3
    return "".join(out)


def _remove_dot_segments(path: str) -> str:
    segments = path.split("/")
    out: list[str] = []
    for seg in segments:
        if seg in ("", "."):
            continue
        if seg == "..":
            if out:
                out.pop()
            continue
        out.append(seg)
    if not out:
        return "/"
    return "/" + "/".join(out)


def _parse_current_query(query: str) -> list[tuple[str, str]]:
    if not query:
        return []
    from urllib.parse import parse_qs

    values = parse_qs(query, keep_blank_values=True)
    pairs: list[tuple[str, str]] = []
    for key in sorted(values.keys()):
        for value in values[key]:
            pairs.append((key, value))
    return pairs


def _encode_current_query(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    return "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in pairs)


def _parse_legacy_query(query: str) -> list[tuple[str, str]]:
    if not query:
        return []
    from urllib.parse import unquote

    pairs: list[tuple[str, str]] = []
    for part in query.split("&"):
        if "=" in part:
            key, val = part.split("=", 1)
        else:
            key, val = part, ""
        pairs.append((unquote(key), unquote(val)))
    return pairs


def normalize_target(profile: ProfileSpec, raw_target: str) -> str:
    if not raw_target:
        raise ValueError("empty target")
    path_part = raw_target
    query_part = ""
    if "?" in raw_target:
        path_part, query_part = raw_target.split("?", 1)

    if not path_part.startswith("/"):
        raise ValueError("path must be absolute")

    path = _decode_path_segments(path_part, profile.uppercase_percent)
    if profile.remove_dot_segments:
        path = _remove_dot_segments(path)
    if profile.uppercase_percent:
        # preserve uppercase percent from decode step
        pass

    if profile.preserve_legacy_query:
        query = query_part
    else:
        pairs = _parse_current_query(query_part)
        query = _encode_current_query(pairs)

    if query:
        return f"{path}?{query}"
    return path


def build_semantic_from_wire(
    *,
    test_name: str,
    profile: ProfileSpec,
    tenant: str,
    key_id: str,
    key_epoch: int,
    method: str,
    authority: str,
    wire_target: str,
    headers: dict[str, list[str]],
    header_order: list[str],
    body: bytes,
    request_nonce: str | None = None,
    request_id: str | None = None,
    pre_verify: bool = False,
) -> SemanticRequest:
    canonical_target = normalize_target(profile, wire_target)
    policy_headers = apply_header_policy(
        headers,
        header_order,
        signature_version=profile.signature_version,
        pre_verify=pre_verify,
    )
    signed_headers = filter_signed_headers(
        policy_headers, signature_version=profile.signature_version
    )
    return SemanticRequest(
        request_id=request_id or seeded_request_id(test_name),
        profile_id=profile.profile_id,
        profile_epoch=profile.epoch,
        signature_version=profile.signature_version,
        tenant=tenant,
        key_id=key_id,
        key_epoch=key_epoch,
        method=normalize_method(method),
        authority=authority,
        wire_target=wire_target,
        canonical_target=canonical_target,
        canonical_headers=signed_headers,
        entity_body=body,
        request_nonce=request_nonce or seeded_nonce(test_name),
    )


def encode_backend_request(sem: SemanticRequest) -> bytes:
    """Deterministic backend wire encoding from semantic authority."""
    lines = [f"{sem.method} {sem.canonical_target} HTTP/1.1"]
    for header in sem.canonical_headers:
        canon = "-".join(part[:1].upper() + part[1:].lower() for part in header.name.split("-"))
        lines.append(f"{canon}: {header.value}")
    lines.append(f"Content-Length: {len(sem.entity_body)}")
    block = "\r\n".join(lines) + "\r\n\r\n"
    return block.encode() + sem.entity_body


def expected_backend_capture(sem: SemanticRequest) -> dict[str, Any]:
    headers: dict[str, str] = {}
    for header in sem.canonical_headers:
        canon = "-".join(part[:1].upper() + part[1:].lower() for part in header.name.split("-"))
        headers[canon] = header.value
    headers["Content-Length"] = str(len(sem.entity_body))
    return {
        "method": sem.method,
        "target": sem.canonical_target,
        "headers": headers,
        "body": sem.entity_body.decode("latin-1") if sem.entity_body else "",
        "body_hex": sem.entity_body.hex(),
    }


def build_raw_request(
    sem: SemanticRequest,
    secret: bytes,
    *,
    extra_headers: list[tuple[str, str]] | None = None,
    chunked: bool = False,
    chunk_size: int | None = None,
) -> bytes:
    signature = sign_semantic(sem, secret)
    lines = [
        f"{sem.method} {sem.wire_target} HTTP/1.1",
        f"Host: {sem.authority}",
        f"X-Sig-Profile: {sem.profile_id}",
        f"X-Sig-Tenant: {sem.tenant}",
        f"X-Sig-Key-Id: {sem.key_id}",
        f"X-Sig-Nonce: {sem.request_nonce}",
        f"X-Request-Id: {sem.request_id}",
    ]
    if extra_headers:
        lines.extend(f"{name}: {value}" for name, value in extra_headers)
    lines.append(f"X-Signature: {signature}")

    body = sem.entity_body
    if chunked:
        lines.append("Transfer-Encoding: chunked")
        lines.append("")
        header_block = "\r\n".join(lines) + "\r\n\r\n"
        chunks: list[bytes] = []
        step = chunk_size or max(1, len(body) // 3 or 1)
        pos = 0
        while pos < len(body):
            part = body[pos : pos + step]
            chunks.append(f"{len(part):x}\r\n".encode() + part + b"\r\n")
            pos += step
        chunks.append(b"0\r\n\r\n")
        return header_block.encode() + b"".join(chunks)

    lines.append(f"Content-Length: {len(body)}")
    lines.append("")
    header_block = "\r\n".join(lines) + "\r\n"
    return header_block.encode() + body


def write_keyring(path, entries: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"keys": entries}, indent=2) + "\n", encoding="utf-8")


def write_profile(path, profile: ProfileSpec) -> None:
    payload = {
        "id": profile.profile_id,
        "epoch": profile.epoch,
        "signature_version": profile.signature_version,
        "preserve_legacy_query": profile.preserve_legacy_query,
        "uppercase_percent": profile.uppercase_percent,
        "remove_dot_segments": profile.remove_dot_segments,
        "header_policy": {},
        "allowed_key_profiles": [profile.profile_id],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_proxy_config(
    path,
    *,
    listen_unix: str,
    backend_unix: str,
    state_dir: str,
    audit_log: str,
    profiles_dir: str,
    keyring_path: str,
    ready_file: str,
    spool_seal_key_hex: str,
    replay_on_start: bool = False,
    body_limit: int = BODY_LIMIT,
) -> None:
    payload = {
        "listen_unix": listen_unix,
        "backend_unix": backend_unix,
        "state_dir": state_dir,
        "spool_dir": f"{state_dir}/spool",
        "audit_log": audit_log,
        "trace_path": "/output/request-trace.json",
        "profiles_dir": profiles_dir,
        "keyring_path": keyring_path,
        "default_profile": "current-2026",
        "body_limit": body_limit,
        "replay_on_start": replay_on_start,
        "ready_file": ready_file,
        "spool_seal_key_hex": spool_seal_key_hex,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
