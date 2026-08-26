from __future__ import annotations

from typing import Any


def clip_bundle_timeline(
    ledger: dict[str, Any],
    dye_reformulations: list[dict[str, Any]],
    epochs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    snapshot = ledger.get("genealogy_snapshot") or {}
    as_of = snapshot.get("as_of_year")
    if as_of is None:
        return list(dye_reformulations), list(epochs)

    as_of_year = int(as_of)
    clipped = [row for row in dye_reformulations if int(row["year"]) <= as_of_year]
    return clipped, list(epochs)
