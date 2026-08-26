from __future__ import annotations

from typing import Any


def preview_venue_span(
    epochs: list[dict[str, Any]],
    school_recitals: list[dict[str, Any]],
) -> float:
    """Recital venue span preview for support tooling (not used in valuation compile)."""
    if not epochs:
        return 0.0
    start = min(int(epoch["from_year"]) for epoch in epochs)
    end = max(int(epoch["to_year"]) for epoch in epochs)
    recital_years = {int(row["year"]) for row in school_recitals}
    covered = sum(1 for year in range(start, end + 1) if year in recital_years)
    span = end - start + 1
    return 100.0 * covered / span if span > 0 else 0.0
