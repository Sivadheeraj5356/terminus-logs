from __future__ import annotations

from typing import Any


def audit_damage_total(
    dye_reformulations: list[dict[str, Any]],
    penalty_rate: float,
) -> float:
    """Additive damage audit helper (not used in valuation compounding)."""
    return sum(penalty_rate * float(row["severity"]) for row in dye_reformulations)
