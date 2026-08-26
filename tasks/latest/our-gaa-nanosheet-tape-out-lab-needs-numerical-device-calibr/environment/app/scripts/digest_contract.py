"""Digest, rounding, and bounds parsing helpers aligned with /app/docs contracts."""

from __future__ import annotations

import hashlib
import math
import struct
import tomllib
from decimal import ROUND_HALF_UP, Decimal

try:
    import tomli  # noqa: F401 — fallback parser for older Python during local dev
except ImportError:
    pass


def round_half_up(value: float, places: int) -> float:
    quant = Decimal("1").scaleb(-places)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def round12(value: float) -> float:
    """Twelve significant-digit rounding for compact-model Id and Cgg outputs only.

    Do not apply to measurement CSV fields stored in calibration_tapeout.json or to
    measure_digest inputs. tapeout digests use raw float parse bits from CSV.
    """
    if value == 0.0:
        return 0.0
    exp = math.floor(math.log10(abs(value)))
    scale = 10 ** (11 - int(exp))
    return round(value * scale) / scale


def float_bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def sha256_hex(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def parse_bounds_toml(raw: str) -> dict:
    return tomllib.loads(raw)


