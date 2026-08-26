"""Resample bin assignment."""

from __future__ import annotations

from dataclasses import dataclass

from cfaxis.formats import Dataset
from cfaxis.formats.io import FreqArg


@dataclass
class BinAssignment:
    bin_index: int
    source_index: int


def assign_bins(ds: Dataset, freq: FreqArg) -> list[BinAssignment]:
    cal = ds.time_axis.calendar
    units = ds.time_axis.units
    raw: list[tuple[int, int]] = []
    for i, inst in enumerate(ds.time_axis.instants):
        y, m, _d = cal.days_from_origin_to_ymd(
            units.origin_year,
            units.origin_month,
            units.origin_day,
            inst.encoded_value,
        )
        if freq == FreqArg.MON:
            key = y * 12 + (m - 1)
        elif freq == FreqArg.SEA:
            season = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2}.get(m, 3)
            key = y * 4 + season
        else:
            key = y
        raw.append((key, i))

    keys = sorted({k for k, _ in raw})
    remap = {k: i for i, k in enumerate(keys)}
    return [
        BinAssignment(bin_index=remap[k], source_index=src) for k, src in raw
    ]


def num_bins(assignments: list[BinAssignment]) -> int:
    if not assignments:
        return 0
    return max(a.bin_index for a in assignments) + 1
