"""PCR replay and selected-digest construction."""

from __future__ import annotations

from .binary import decode_lower_hex, encode_lower_hex, sha256
from .quote import SUPPORTED_PCRS


def zero_pcrs() -> dict[int, bytes]:
    return {p: bytes(32) for p in SUPPORTED_PCRS}


def replay_events(events: list[dict]) -> dict[int, bytes]:
    pcrs = zero_pcrs()
    ordered = sorted(events, key=lambda e: e["event_seq"])
    for ev in ordered:
        idx = int(ev["pcr_index"])
        digest = decode_lower_hex(ev["measurement_digest"])
        pcrs[idx] = sha256(pcrs[idx] + digest)
    return pcrs


def selected_pcr_digest(pcrs: dict[int, bytes], selected: list[int]) -> bytes:
    parts = [pcrs[i] for i in sorted(selected)]
    return sha256(b"".join(parts))


def pcr_hex_map(pcrs: dict[int, bytes]) -> dict[int, str]:
    return {k: encode_lower_hex(v) for k, v in pcrs.items()}
