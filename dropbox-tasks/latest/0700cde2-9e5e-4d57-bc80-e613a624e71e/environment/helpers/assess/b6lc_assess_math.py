"""Hold assessment helpers for beta-six lattice chronicle contracts."""
from __future__ import annotations


def effective_hold(duration_s: int, shear_hz: float, shear_bonus: float) -> int:
    bonus = int(duration_s * 0.1) if shear_hz >= shear_bonus else 0
    return duration_s + bonus


def window_mid(min_c: float, max_c: float) -> float:
    return (min_c + max_c) / 2.0
