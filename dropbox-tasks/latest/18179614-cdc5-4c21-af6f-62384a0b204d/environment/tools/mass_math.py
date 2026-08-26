#!/usr/bin/env python3
"""Local numeric helpers for mass-transfer digests (stdlib only)."""
from __future__ import annotations

import hashlib
import math


def logsumexp(values: list[float]) -> float:
    m = max(values)
    if not math.isfinite(m):
        return m
    return m + math.log(sum(math.exp(v - m) for v in values))


def plan_digest_hex(plan: list[list[float]]) -> str:
    parts = [f"{i},{j}:{plan[i][j]:.17e}" for i in range(len(plan)) for j in range(len(plan[0]))]
    return hashlib.sha256(";".join(parts).encode()).hexdigest()


def instance_digest_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
