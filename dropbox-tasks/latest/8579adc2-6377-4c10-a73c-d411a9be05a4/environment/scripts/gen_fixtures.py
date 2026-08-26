#!/usr/bin/env python3
from __future__ import annotations

import struct
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "testdata"
SCRIPTS_VALID = OUT / "scripts" / "valid"
SCRIPTS_BOUNDARY = OUT / "scripts" / "boundary"
WIRE_VALID = OUT / "wire" / "valid"

FRAME_DATA = 0
FRAME_HEADERS = 1
FRAME_SETTINGS = 2
FRAME_RST_STREAM = 3
FRAME_GOAWAY = 4
FRAME_PING = 5
FRAME_WINDOW_UPDATE = 6

FLAG_END_HEADERS = 0x4


def write_script(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(("\n".join(lines) + "\n").encode("utf-8"))


def encode_varint(value: int) -> bytes:
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def encode_header_block(fields: list[tuple[str, str]]) -> bytes:
    out = bytearray()
    for name, value in fields:
        name_bytes = name.encode("utf-8")
        value_bytes = value.encode("utf-8")
        out += encode_varint(len(name_bytes))
        out += name_bytes
        out += encode_varint(len(value_bytes))
        out += value_bytes
    return bytes(out)


def frame_header(length: int, frame_type: int, flags: int, stream_id: int) -> bytes:
    return (
        struct.pack(">I", length)[1:]
        + bytes([frame_type, flags])
        + struct.pack(">I", stream_id)
    )


def write_wire(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def gen_valid_scripts() -> None:
    write_script(
        SCRIPTS_VALID / "valid_001.script",
        [
            "session 65536 500",
            "stream 1",
            "add_header 1 :method GET",
            "add_header 1 :path /",
            "flush 1",
        ],
    )
    write_script(
        SCRIPTS_VALID / "valid_002.script",
        [
            "session 65536 500",
            "stream 1",
            "add_header 1 host example.test",
            "add_header 1 accept text/html",
            "add_header 1 accept-language en-US",
            "flush 1",
        ],
    )
    write_script(
        SCRIPTS_VALID / "valid_003.script",
        [
            "session 65536 500",
            "stream 1",
            "stream 3",
            "add_header 1 :method GET",
            "add_header 3 :method POST",
            "flush 1",
            "flush 3",
        ],
    )
    write_script(
        SCRIPTS_VALID / "valid_004.script",
        [
            "session 65536 500",
            "stream 1",
            "add_header 1 :method GET",
            "add_header 1 :path /orders",
            "flush 1",
            "start_headers 1 trailers",
            "add_header 1 x-checksum abc123",
            "flush 1",
        ],
    )
    write_script(
        SCRIPTS_VALID / "valid_005.script",
        [
            "session 65536 500",
            "stream 1",
            "start_headers 1 informational",
            "add_header 1 :status 103",
            "flush 1",
            "start_headers 1 headers",
            "add_header 1 :status 200",
            "add_header 1 content-type application/json",
            "flush 1",
        ],
    )
    write_script(
        SCRIPTS_VALID / "valid_006.script",
        [
            "session 65536 500",
            "stream 1",
            "stream 3",
            "stream 5",
            "destroy 1",
            "destroy 3",
            "destroy 5",
        ],
    )
    lines = ["session 65536 500", "stream 1"]
    for i in range(20):
        lines.append(f"add_header 1 x-tag-{i} value-{i}")
    lines.append("flush 1")
    write_script(SCRIPTS_VALID / "valid_007.script", lines)

    lines = ["session 65536 500"]
    for sid in (1, 3, 5, 7):
        lines.append(f"stream {sid}")
        lines.append(f"add_header {sid} :method GET")
        lines.append(f"add_header {sid} :path /item/{sid}")
        lines.append(f"flush {sid}")
        lines.append(f"destroy {sid}")
    write_script(SCRIPTS_VALID / "valid_008.script", lines)


def gen_boundary_scripts() -> None:
    write_script(
        SCRIPTS_BOUNDARY / "boundary_empty_value.script",
        [
            "session 65536 500",
            "stream 1",
            "add_header 1 x-empty-value -",
            "flush 1",
        ],
    )

    name = "x-exact"
    value = "0123456789"
    charge = len(name) + len(value) + 32
    write_script(
        SCRIPTS_BOUNDARY / "boundary_exact_byte_cap.script",
        [
            f"session {charge} 500",
            "stream 1",
            f"add_header 1 {name} {value}",
            "add_header 1 second-header x",
        ],
    )

    write_script(
        SCRIPTS_BOUNDARY / "boundary_exact_count_cap.script",
        [
            "session 1048576 5",
            "stream 1",
            "add_header 1 h0 v0",
            "add_header 1 h1 v1",
            "add_header 1 h2 v2",
            "add_header 1 h3 v3",
            "add_header 1 h4 v4",
            "add_header 1 h5 v5",
        ],
    )

    write_script(
        SCRIPTS_BOUNDARY / "boundary_clean_destroy.script",
        [
            "session 65536 500",
            "stream 1",
            "destroy 1",
        ],
    )

    write_script(
        SCRIPTS_BOUNDARY / "boundary_phase_order_rejected.script",
        [
            "session 65536 500",
            "stream 1",
            "start_headers 1 informational",
            "add_header 1 :status 103",
            "flush 1",
            "start_headers 1 headers",
            "add_header 1 :status 200",
            "start_headers 1 informational",
            "add_header 1 content-type application/json",
            "flush 1",
        ],
    )


def gen_wire_captures() -> None:
    ping_payload = struct.pack(">Q", 0x0102030405060708)
    write_wire(
        WIRE_VALID / "ping.bin", frame_header(8, FRAME_PING, 0, 0) + ping_payload
    )

    window_payload = struct.pack(">I", 65535)
    write_wire(
        WIRE_VALID / "window_update.bin",
        frame_header(4, FRAME_WINDOW_UPDATE, 0, 1) + window_payload,
    )

    header_block = encode_header_block(
        [(":method", "GET"), (":path", "/"), ("host", "example.test")]
    )
    write_wire(
        WIRE_VALID / "headers.bin",
        frame_header(len(header_block), FRAME_HEADERS, FLAG_END_HEADERS, 1)
        + header_block,
    )


def main() -> None:
    gen_valid_scripts()
    gen_boundary_scripts()
    gen_wire_captures()


if __name__ == "__main__":
    main()
