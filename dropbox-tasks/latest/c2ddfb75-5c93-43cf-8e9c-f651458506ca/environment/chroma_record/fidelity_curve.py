from __future__ import annotations

from typing import Any


def compound_dye_fidelity(
    dye_reformulations: list[dict[str, Any]],
    penalty_rate: float,
) -> float:
    penalty_total = 0.0
    for event in sorted(dye_reformulations, key=lambda row: int(row["year"])):
        penalty_total += penalty_rate * float(event["severity"])
    return max(0.0, 1.0 - penalty_total)
