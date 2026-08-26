from __future__ import annotations

from typing import Any


def gated_reformulations(
    dye_reformulations: list[dict[str, Any]],
    epochs: list[dict[str, Any]],
    school_recitals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    active_years: set[int] = set()
    for epoch in epochs:
        active_years.update(range(int(epoch["from_year"]), int(epoch["to_year"]) + 1))
    return [row for row in dye_reformulations if int(row["year"]) in active_years]
