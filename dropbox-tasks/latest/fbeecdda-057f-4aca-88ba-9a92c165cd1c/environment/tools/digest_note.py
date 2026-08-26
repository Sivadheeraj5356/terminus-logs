"""Calibration note: digest and climate arithmetic homes for verifier alignment."""

from __future__ import annotations

import hashlib
import math


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def climate_scale(alpha: float, temp_c: float, rh_pct: float, t0: float = 20.0, h0: float = 50.0, beta: float = 0.012) -> float:
    return math.exp(alpha * (temp_c - t0)) * (1.0 + beta * (rh_pct - h0) / 100.0)
