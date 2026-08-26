"""Shared digest helpers for coupled mode-gap SHA-256 encoding."""

from __future__ import annotations

import hashlib

NEXT = {"M1": "M2", "M2": "M3", "M3": "M4", "M4": "M1"}


def fmt6(value: float) -> str:
    rounded = round(value, 6)
    if rounded == 0.0:
        rounded = 0.0
    return f"{rounded:.6f}"


def scale(
    mode: str,
    excit: float,
    stiff: dict[str, float],
    damp: dict[str, float],
    cpl: dict[str, float],
    weight: float,
) -> float:
    nxt = NEXT[mode]
    return weight * excit * (
        stiff[mode] * damp[mode] + cpl[mode] * stiff[nxt] * damp[nxt]
    )


def mode_gap(
    omega_obs: float,
    omega_ref: float,
    mode: str,
    excit: float,
    stiff: dict[str, float],
    damp: dict[str, float],
    cpl: dict[str, float],
    weight: float,
) -> float:
    return (omega_obs - omega_ref) - scale(mode, excit, stiff, damp, cpl, weight)


def digest_hex(panel_gaps: dict[str, list[float]]) -> str:
    parts = []
    for panel_id in sorted(panel_gaps):
        joined = ",".join(fmt6(v) for v in panel_gaps[panel_id])
        parts.append(f"{panel_id}:{joined}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def chain_digest(full: str, perm: str, rev: str, compose: str) -> str:
    blob = f"{full}|{perm}|{rev}|{compose}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
