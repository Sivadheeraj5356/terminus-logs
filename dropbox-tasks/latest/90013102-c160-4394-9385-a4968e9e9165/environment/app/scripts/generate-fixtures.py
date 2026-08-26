#!/usr/bin/env python3
"""Generate signed HTTP fixture bytes for public demos."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

SECRET = b"demo-hmac-secret-key-for-public-tests!!"


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def v2_message(sem: dict) -> str:
    lines = ["LOCAL-SIG-V2"]
    lines.append(f"profile:{sem['profile_id']}@{sem['profile_epoch']}")
    lines.append(f"key:{sem['tenant']}/{sem['key_id']}@{sem['key_epoch']}")
    lines.append(f"method:{sem['method']}")
    lines.append(f"authority:{sem['authority']}")
    lines.append(f"target:{sem['canonical_target']}")
    headers = sem["canonical_headers"]
    lines.append(f"headers:{len(headers)}")
    for h in headers:
        lines.append(f"{h['name']}:{h['value']}")
    lines.append(f"body-sha256:{sem['entity_body_sha256']}")
    lines.append(f"body-length:{sem['entity_body_length']}")
    lines.append(f"nonce:{sem['request_nonce']}")
    return "\n".join(lines) + "\n"


def v1_message(sem: dict) -> str:
    lines = ["LOCAL-SIG-V1"]
    lines.append(f"tenant:{sem['tenant']}")
    lines.append(f"key:{sem['key_id']}@{sem['key_epoch']}")
    lines.append(f"profile:{sem['profile_id']}")
    lines.append(f"{sem['method']} {sem['canonical_target']}")
    lines.append(f"host:{sem['authority']}")
    for h in sem["canonical_headers"]:
        lines.append(f"h:{h['name']}={h['value']}")
    lines.append(f"body:{sem['entity_body_sha256']}:{sem['entity_body_length']}")
    lines.append(f"nonce:{sem['request_nonce']}")
    return "\n".join(lines) + "\n"


def sign(version: int, sem: dict) -> str:
    msg = v1_message(sem) if version == 1 else v2_message(sem)
    sig = hmac.new(SECRET, msg.encode(), hashlib.sha256).hexdigest()
    return f"v{version} {sig}"


def build_request(sem: dict, version: int, extra_wire_headers: list[tuple[str, str]], body: bytes) -> bytes:
    lines = [
        f"{sem['method']} {sem['wire_target']} HTTP/1.1",
        f"Host: {sem['authority']}",
        f"X-Sig-Profile: {sem['profile_id']}",
        f"X-Sig-Tenant: {sem['tenant']}",
        f"X-Sig-Key-Id: {sem['key_id']}",
        f"X-Sig-Nonce: {sem['request_nonce']}",
        f"X-Request-Id: {sem['request_id']}",
    ]
    for name, value in extra_wire_headers:
        lines.append(f"{name}: {value}")
    for h in sem.get("wire_headers", []):
        lines.append(f"{h['name']}: {h['value']}")
    sig = sign(version, sem)
    lines.append(f"X-Signature: {sig}")
    if sem.get("chunked"):
        lines.append("Transfer-Encoding: chunked")
        lines.append("")
        chunks = []
        pos = 0
        step = sem.get("chunk_size", max(1, len(body) // 2))
        while pos < len(body):
            part = body[pos : pos + step]
            chunks.append(f"{len(part):x}\r\n".encode() + part + b"\r\n")
            pos += step
        chunks.append(b"0\r\n\r\n")
        header_block = "\r\n".join(lines) + "\r\n\r\n"
        return header_block.encode() + b"".join(chunks)
    lines.append(f"Content-Length: {len(body)}")
    lines.append("")
    header_block = "\r\n".join(lines) + "\r\n"
    return header_block.encode() + body


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "data" / "requests"
    out_dir.mkdir(parents=True, exist_ok=True)

    simple_current = {
        "request_id": "req-simple-current",
        "profile_id": "current-2026",
        "profile_epoch": 1,
        "tenant": "demo",
        "key_id": "demo-key-1",
        "key_epoch": 1,
        "method": "POST",
        "authority": "api.local",
        "wire_target": "/v1/items",
        "canonical_target": "/v1/items",
        "canonical_headers": [
            {"name": "host", "value": "api.local"},
            {"name": "content-type", "value": "application/json"},
        ],
        "entity_body_sha256": body_digest(b'{"item":1}'),
        "entity_body_length": 10,
        "request_nonce": "nonce-current-1",
        "wire_headers": [{"name": "Content-Type", "value": "application/json"}],
    }
    (out_dir / "simple-current.http").write_bytes(
        build_request(simple_current, 2, [], b'{"item":1}')
    )

    duplicate = dict(simple_current)
    duplicate["request_id"] = "req-duplicate-current"
    duplicate["wire_target"] = "/v1/shadow"
    duplicate["canonical_target"] = "/v1/shadow"
    duplicate["canonical_headers"] = [
        {"name": "host", "value": "api.local"},
        {"name": "content-type", "value": "application/json"},
        {"name": "accept", "value": "text/plain, application/json"},
    ]
    duplicate["request_nonce"] = "nonce-duplicate-1"
    duplicate["entity_body_sha256"] = body_digest(b"")
    duplicate["entity_body_length"] = 0
    duplicate["method"] = "GET"
    duplicate.pop("wire_headers", None)
    # pre-filter signing matches broken verifier path (includes connection-nominated x-shadow)
    duplicate_pre = dict(duplicate)
    duplicate_pre["canonical_headers"] = [
        {"name": "host", "value": "api.local"},
        {"name": "content-type", "value": "application/json"},
        {"name": "accept", "value": "text/plain, application/json"},
        {"name": "x-shadow", "value": "injected"},
    ]
    (out_dir / "duplicate-list-current.http").write_bytes(
        build_request(
            duplicate_pre,
            2,
            [
                ("Connection", "x-shadow"),
                ("X-Shadow", "injected"),
                ("Accept", "text/plain"),
                ("Accept", " application/json"),
                ("Content-Type", "application/json"),
            ],
            b"",
        )
    )

    encoded = dict(simple_current)
    encoded["request_id"] = "req-encoded-current"
    encoded["wire_target"] = "/v1/%66oo/bar%2Finish?q=1&q="
    encoded["canonical_target"] = "/v1/%66oo/bar%2Finish?q=1&q="
    encoded["method"] = "GET"
    encoded["entity_body_sha256"] = body_digest(b"")
    encoded["entity_body_length"] = 0
    encoded["request_nonce"] = "nonce-encoded-1"
    encoded["canonical_headers"] = [{"name": "host", "value": "api.local"}]
    encoded.pop("wire_headers", None)
    (out_dir / "encoded-target-current.http").write_bytes(
        build_request(encoded, 2, [], b"")
    )

    legacy = {
        "request_id": "req-simple-legacy",
        "profile_id": "legacy-2024",
        "profile_epoch": 1,
        "tenant": "demo",
        "key_id": "demo-key-1",
        "key_epoch": 1,
        "method": "GET",
        "authority": "legacy.local",
        "wire_target": "/health",
        "canonical_target": "/health",
        "canonical_headers": [{"name": "host", "value": "legacy.local"}],
        "entity_body_sha256": body_digest(b""),
        "entity_body_length": 0,
        "request_nonce": "nonce-legacy-1",
    }
    (out_dir / "simple-legacy.http").write_bytes(build_request(legacy, 1, [], b""))

    expected_dir = Path(__file__).resolve().parent.parent / "data" / "expected-public"
    expected_dir.mkdir(parents=True, exist_ok=True)
    (expected_dir / "simple-current.backend.json").write_text(
        json.dumps(
            {
                "method": "POST",
                "target": "/v1/items",
                "headers": {
                    "Host": "api.local",
                    "Content-Type": "application/json",
                    "Content-Length": "10",
                },
                "body": '{"item":1}',
            },
            indent=2,
        )
        + "\n"
    )
    (expected_dir / "simple-legacy.backend.json").write_text(
        json.dumps(
            {
                "method": "GET",
                "target": "/health",
                "headers": {"Host": "legacy.local", "Content-Length": "0"},
                "body": "",
            },
            indent=2,
        )
        + "\n"
    )
    print("generated fixtures", file=sys.stderr)


if __name__ == "__main__":
    main()
