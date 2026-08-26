from __future__ import annotations

from collections.abc import Callable
from typing import Any


def slice_custody_epochs(
    epochs: list[dict[str, Any]],
    replay_floor: int,
) -> list[dict[str, Any]]:
    if replay_floor <= 1:
        return list(epochs)
    skip = replay_floor - 1
    if skip >= len(epochs):
        return []
    return epochs[skip:]


def _owner_for_year(epochs: list[dict[str, Any]], year: int) -> str | None:
    for epoch in epochs:
        if int(epoch["from_year"]) <= year <= int(epoch["to_year"]):
            return str(epoch["owner_id"])
    return None


def school_continuity_span(
    epochs: list[dict[str, Any]],
    certs: list[dict[str, Any]],
    sales: list[dict[str, Any]],
    relay_check: Callable[[list[dict[str, Any]], int, str, str], bool],
    replay_floor: int = 0,
) -> float:
    _ = sales
    _ = relay_check
    _ = replay_floor
    if not epochs:
        return 0.0
    start = min(int(epoch["from_year"]) for epoch in epochs)
    end = max(int(epoch["to_year"]) for epoch in epochs)
    span = end - start + 1
    if span <= 0:
        return 0.0

    anchor_owner = _owner_for_year(epochs, end)
    covered = 0
    for year in range(start, end + 1):
        if anchor_owner is None:
            continue
        for cert in certs:
            if cert["holder"] != anchor_owner:
                continue
            if int(cert["issued_year"]) <= year <= int(cert["expires_year"]):
                covered += 1
                break
    return 100.0 * covered / span
