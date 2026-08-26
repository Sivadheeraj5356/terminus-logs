"""Shared CSV contract for Unity ink reconciliation reports."""

from __future__ import annotations

REPORT_FIELDS = ["settlement_id", "amount_decimal", "radix_base", "min_ink"]
INPUT_FIELDS = ["settlement_id", "amount_decimal", "radix_base"]


def normalize_amount(raw: str) -> str:
    value = raw.strip()
    if not value or not value.isdecimal():
        raise ValueError(f"invalid amount_decimal {raw!r}")
    return value.lstrip("0") or "0"


def parse_radix(raw: str) -> int:
    base = int(raw)
    if not 2 <= base <= 16:
        raise ValueError(f"radix_base out of range: {raw!r}")
    return base
