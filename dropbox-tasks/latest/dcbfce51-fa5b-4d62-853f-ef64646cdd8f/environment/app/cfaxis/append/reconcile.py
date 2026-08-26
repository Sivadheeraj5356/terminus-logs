"""Dataset append and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cfaxis.error import IncompatibleAppendError
from cfaxis.formats import Dataset, write_ccf
from cfaxis.time import TimeAxis


@dataclass
class _Row:
    ordinal: int
    encoded_in_base: float
    is_tail: bool
    src_idx: int


def append_datasets(base: Dataset, tail: Dataset, out_path: Path) -> None:
    if base.time_axis.calendar != tail.time_axis.calendar:
        raise IncompatibleAppendError(
            f"calendar mismatch: {base.time_axis.calendar.as_str()} vs "
            f"{tail.time_axis.calendar.as_str()}"
        )

    cal = base.time_axis.calendar
    base_units = base.time_axis.units
    tail_units = tail.time_axis.units

    rows: list[_Row] = []
    for idx, inst in enumerate(base.time_axis.instants):
        y, m, d = cal.days_from_origin_to_ymd(
            base_units.origin_year,
            base_units.origin_month,
            base_units.origin_day,
            inst.encoded_value,
        )
        rows.append(
            _Row(
                ordinal=cal.canonical_ordinal(y, m, d),
                encoded_in_base=inst.encoded_value,
                is_tail=False,
                src_idx=idx,
            )
        )
    for idx, inst in enumerate(tail.time_axis.instants):
        y, m, d = cal.days_from_origin_to_ymd(
            tail_units.origin_year,
            tail_units.origin_month,
            tail_units.origin_day,
            inst.encoded_value,
        )
        rows.append(
            _Row(
                ordinal=cal.canonical_ordinal(y, m, d),
                encoded_in_base=cal.ymd_to_encoded_days(base_units, y, m, d),
                is_tail=True,
                src_idx=idx,
            )
        )

    rows.sort(key=lambda r: (r.ordinal, r.is_tail))

    time_vals = [r.encoded_in_base for r in rows]
    merged = _clone_dataset(base)
    merged.header.time = time_vals
    merged.time_axis = TimeAxis.from_values(cal, base_units, time_vals)

    for vb, vt in zip(base.variables, tail.variables, strict=True):
        elem = 8
        out = bytearray(len(rows) * elem)
        for out_i, row in enumerate(rows):
            src = vt if row.is_tail else vb
            src_off = row.src_idx * elem
            dst_off = out_i * elem
            out[dst_off : dst_off + elem] = src.bytes[src_off : src_off + elem]
        for vm in merged.variables:
            if vm.name == vb.name:
                vm.bytes = bytes(out)
                vm.def_.count = len(merged.time_axis.instants)
                if vm.name in merged.header.variables:
                    merged.header.variables[vm.name].count = len(
                        merged.time_axis.instants
                    )
                break

    merged.sync_header_from_axes()

    tmp = out_path.with_suffix(".ccf.partial")
    write_ccf(tmp, merged)
    tmp.replace(out_path)


def _clone_dataset(ds: Dataset) -> Dataset:
    from copy import deepcopy

    return deepcopy(ds)
