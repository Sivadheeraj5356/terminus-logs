"""Merge climate members onto one CF calendar-qualified axis."""

from __future__ import annotations

import struct

from cfaxis.error import IncompatibleAppendError, ValidationError
from cfaxis.formats.common import (
    CcfHeader,
    Dataset,
    VariableData,
    VariableDef,
)
from cfaxis.time import BoundsAxis, TimeAxis


def _read_f64(buf: bytes, idx: int) -> float:
    start = idx * 8
    return struct.unpack_from("<d", buf, start)[0]


def _write_f64_list(vals: list[float]) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)


def _canonical_ymd(ds: Dataset, encoded: float) -> tuple[int, int, int]:
    cal = ds.time_axis.calendar
    units = ds.time_axis.units
    return cal.days_from_origin_to_ymd(
        units.origin_year, units.origin_month, units.origin_day, encoded
    )


def _ordinal(ds: Dataset, encoded: float) -> int:
    y, m, d = _canonical_ymd(ds, encoded)
    return ds.time_axis.calendar.canonical_ordinal(y, m, d)


def _row_payload(ds: Dataset, idx: int) -> tuple[tuple[float, ...], tuple[float, float] | None]:
    vals = tuple(_read_f64(v.bytes, idx) for v in ds.variables)
    bounds = None
    if ds.bounds_axis is not None:
        pair = ds.bounds_axis.encoded_pairs()[idx]
        bounds = (pair[0], pair[1])
    return vals, bounds


def merge_datasets(base: Dataset | None, shards: list[Dataset]) -> Dataset:
    if base is None and not shards:
        raise ValidationError("nothing to compact")
    if base is None:
        base = shards[0]
        shards = shards[1:]

    cal = base.time_axis.calendar
    for shard in shards:
        if shard.time_axis.calendar != cal:
            raise IncompatibleAppendError(
                f"calendar mismatch: {cal.as_str()} vs {shard.time_axis.calendar.as_str()}"
            )

    archive_units = base.time_axis.units
    rows: list[tuple[int, float, tuple[float, ...], tuple[float, float] | None, str]] = []

    def _ingest(ds: Dataset, tag: str) -> None:
        for i, inst in enumerate(ds.time_axis.instants):
            y, m, d = _canonical_ymd(ds, inst.encoded_value)
            enc = cal.ymd_to_encoded_days(archive_units, y, m, d)
            ord_ = cal.canonical_ordinal(y, m, d)
            payload, bounds = _row_payload(ds, i)
            if bounds is not None:
                lo_y, lo_m, lo_d = _canonical_ymd(ds, bounds[0])
                hi_y, hi_m, hi_d = _canonical_ymd(ds, bounds[1])
                bounds = (
                    cal.ymd_to_encoded_days(archive_units, lo_y, lo_m, lo_d),
                    cal.ymd_to_encoded_days(archive_units, hi_y, hi_m, hi_d),
                )
            rows.append((ord_, enc, payload, bounds, tag))

    _ingest(base, "base")
    for i, shard in enumerate(shards):
        _ingest(shard, f"shard{i}")

    rows.sort(key=lambda r: (r[0], r[4]))

    merged: list[tuple[int, float, tuple[float, ...], tuple[float, float] | None]] = []
    seen: set[int] = set()
    for ord_, enc, payload, bounds, _tag in rows:
        if ord_ in seen:
            continue
        seen.add(ord_)
        merged.append((ord_, enc, payload, bounds))

    time_vals = [enc for _, enc, _, _ in merged]
    time_axis = TimeAxis.from_values(cal, archive_units, time_vals)

    var_names = [v.name for v in base.variables]
    var_aggs = {v.name: v.def_.agg for v in base.variables}
    n = len(merged)
    variables: list[VariableData] = []
    var_defs: dict[str, VariableDef] = {}
    offset = 0
    for name in var_names:
        col = [payload[var_names.index(name)] for _, _, payload, _ in merged]
        raw = _write_f64_list(col)
        defn = VariableDef(dtype="f64", offset=offset, count=n, agg=var_aggs[name])
        var_defs[name] = defn
        variables.append(VariableData(name=name, def_=defn, bytes=raw))
        offset += n * 8

    bounds_pairs = None
    bounds_axis = None
    if merged and all(b is not None for _, _, _, b in merged):
        bounds_pairs = [[b[0], b[1]] for _, _, _, b in merged]  # type: ignore[index]
        bounds_axis = BoundsAxis.from_pairs(cal, archive_units, bounds_pairs)

    header = CcfHeader(
        schema_version=1,
        calendar=cal.as_str(),
        units=archive_units.echo(),
        time=time_vals,
        variables=var_defs,
        bounds=bounds_pairs,
    )
    return Dataset(
        header=header,
        time_axis=time_axis,
        bounds_axis=bounds_axis,
        variables=variables,
        global_attrs=dict(base.global_attrs),
    )


def datasets_equal_at_instant(a: Dataset, ai: int, b: Dataset, bi: int) -> bool:
    """Compare two observations for semantic equality."""
    if _ordinal(a, a.time_axis.instants[ai].encoded_value) != _ordinal(
        b, b.time_axis.instants[bi].encoded_value
    ):
        return False
    pa, ba = _row_payload(a, ai)
    pb, bb = _row_payload(b, bi)
    return pa == pb and ba == bb
