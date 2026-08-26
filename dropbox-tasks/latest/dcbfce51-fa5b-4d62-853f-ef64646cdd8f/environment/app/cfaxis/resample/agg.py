"""Resample aggregation."""

from __future__ import annotations

import struct

from cfaxis.formats.common import (
    AggKind,
    CcfHeader,
    Dataset,
    VariableData,
    VariableDef,
)
from cfaxis.formats.io import FreqArg
from cfaxis.resample.bins import BinAssignment, num_bins
from cfaxis.time import TimeAxis


def aggregate_bins(
    ds: Dataset,
    assignments: list[BinAssignment],
    _freq: FreqArg,
) -> Dataset:
    n_bins = num_bins(assignments)
    bin_values: dict[int, list[int]] = {}
    for a in assignments:
        bin_values.setdefault(a.bin_index, []).append(a.source_index)

    new_time: list[float] = []
    for b in range(n_bins):
        indices = bin_values.get(b, [])
        if not indices:
            new_time.append(0.0)
        else:
            encoded = sum(
                ds.time_axis.instants[si].encoded_value for si in indices
            ) / len(indices)
            new_time.append(encoded)

    cal = ds.time_axis.calendar
    units = ds.time_axis.units
    time_axis = TimeAxis.from_values(cal, units, new_time)

    variables: list[VariableData] = []
    var_defs: dict[str, VariableDef] = {}
    offset = 0
    for v in ds.variables:
        agg_vals = [0.0] * n_bins
        counts = [0] * n_bins
        for bin_idx, indices in bin_values.items():
            for si in indices:
                val = _read_f64_at(v.bytes, si)
                if v.def_.agg == AggKind.SUM:
                    agg_vals[bin_idx] += val
                elif v.def_.agg == AggKind.MEAN:
                    agg_vals[bin_idx] += val
                    counts[bin_idx] += 1
                elif v.def_.agg == AggKind.MIN:
                    if counts[bin_idx] == 0 or val < agg_vals[bin_idx]:
                        agg_vals[bin_idx] = val
                    counts[bin_idx] += 1
                elif v.def_.agg == AggKind.MAX:
                    if counts[bin_idx] == 0 or val > agg_vals[bin_idx]:
                        agg_vals[bin_idx] = val
                    counts[bin_idx] += 1
        for bin_idx, c in enumerate(counts):
            if c > 0 and v.def_.agg == AggKind.MEAN:
                agg_vals[bin_idx] /= c
        bytes_ = _f64_vec_to_bytes(agg_vals)
        def_ = VariableDef(
            dtype="f64",
            offset=offset,
            count=n_bins,
            agg=v.def_.agg,
        )
        var_defs[v.name] = def_
        variables.append(VariableData(name=v.name, def_=def_, bytes=bytes_))
        offset += n_bins * 8

    header = CcfHeader(
        schema_version=1,
        calendar=ds.header.calendar,
        units=ds.header.units,
        time=new_time,
        bounds=None,
        variables=var_defs,
    )

    return Dataset(
        header=header,
        time_axis=time_axis,
        bounds_axis=None,
        variables=variables,
        global_attrs=dict(ds.global_attrs),
    )


def _read_f64_at(bytes_: bytes, idx: int) -> float:
    start = idx * 8
    return struct.unpack_from("<d", bytes_, start)[0]


def _f64_vec_to_bytes(vals: list[float]) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)
