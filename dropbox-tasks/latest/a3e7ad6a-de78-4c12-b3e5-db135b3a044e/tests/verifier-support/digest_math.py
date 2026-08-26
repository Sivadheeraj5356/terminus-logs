"""Independent digest math for verifier — mirrors /app/scripts/digest_probe.py."""

from __future__ import annotations

import hashlib


def hex_sha256_utf8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def epoch_seal(lattice_digest: str, epoch: int, scenario_id: str, topo_rev: str) -> str:
    return hex_sha256_utf8(f"{lattice_digest}|{epoch}|{scenario_id}|{topo_rev}")


def window_digest(decisions: list[dict]) -> str:
    lines = []
    for d in sorted(decisions, key=lambda x: x["id"]):
        w = d.get("window") or {}
        ex = "1" if d.get("exclusive") else "0"
        lines.append(f"{d['id']}|{int(w.get('start', 0))}|{int(w.get('end', 0))}|{ex}")
    return hex_sha256_utf8("\n".join(lines))


def booking_digest(bookings: list[dict]) -> str:
    lines = [
        f"{b['pool']}|{b['decision_id']}|{int(b['start'])}|{int(b['end'])}"
        for b in bookings
    ]
    lines.sort()
    return hex_sha256_utf8("\n".join(lines))
