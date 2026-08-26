"""CFT text format."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from cfaxis.error import FormatError, ParseError
from cfaxis.formats.common import (
    AggKind,
    CcfHeader,
    Dataset,
    VariableData,
    VariableDef,
)
from cfaxis.time import BoundsAxis, Calendar, TimeAxis, UnitsOrigin


def read_cft(path: Path) -> Dataset:
    text = path.read_text()
    meta: dict[str, str] = {}
    csv_start = 0
    for i, line in enumerate(text.splitlines()):
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            if "=" in body:
                k, v = body.split("=", 1)
                meta[k.strip()] = v.strip()
        elif line.strip():
            csv_start = i
            break

    calendar_s = meta.get("calendar", "gregorian")
    units_s = meta.get("units")
    if units_s is None:
        raise FormatError("CFT missing units")

    lines = text.splitlines()[csv_start:]
    if not lines:
        raise FormatError("CFT missing CSV section")
    cols = [c.strip() for c in lines[0].split(",")]
    try:
        time_idx = cols.index("time")
    except ValueError:
        raise FormatError("CFT missing time column") from None

    var_names = [c for i, c in enumerate(cols) if i != time_idx and c]

    time_vals: list[float] = []
    var_cols: dict[str, list[float]] = {name: [] for name in var_names}

    var_indices = [
        i for i, _ in enumerate(cols) if i != time_idx
    ]

    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) != len(cols):
            raise FormatError("CFT row width mismatch")
        try:
            t = float(parts[time_idx].strip())
        except ValueError as e:
            raise ParseError(f"time: {e}") from e
        time_vals.append(t)
        for name, idx in zip(var_names, var_indices, strict=True):
            try:
                v = float(parts[idx].strip())
            except ValueError as e:
                raise ParseError(f"{name}: {e}") from e
            var_cols[name].append(v)

    cal = Calendar.from_str(calendar_s)
    units = UnitsOrigin.parse(units_s)
    time_axis = TimeAxis.from_values(cal, units, time_vals)

    n = len(time_vals)
    variables: list[VariableData] = []
    offset = 0
    var_defs: dict[str, VariableDef] = {}
    for name in var_names:
        values = var_cols[name]
        bytes_ = _f64_vec_to_bytes(values)
        def_ = VariableDef(
            dtype="f64",
            offset=offset,
            count=n,
            agg=AggKind.SUM if name == "precip" else AggKind.MEAN,
        )
        var_defs[name] = def_
        variables.append(VariableData(name=name, def_=def_, bytes=bytes_))
        offset += n * 8

    bounds_axis = None
    if "bounds" in meta:
        try:
            pairs: list[list[float]] = json.loads(meta["bounds"])
            bounds_axis = BoundsAxis.from_pairs(cal, units, pairs)
        except (json.JSONDecodeError, TypeError):
            bounds_axis = None

    header = CcfHeader(
        schema_version=1,
        calendar=calendar_s,
        units=units_s,
        time=time_vals,
        bounds=bounds_axis.encoded_pairs() if bounds_axis else None,
        variables=var_defs,
    )

    return Dataset(
        header=header,
        time_axis=time_axis,
        bounds_axis=bounds_axis,
        variables=variables,
        global_attrs=meta,
    )


def write_cft(path: Path, ds: Dataset) -> None:
    if ds.time_axis.instants:
        calendar = ds.time_axis.instants[0].echo_calendar()
        units = ds.time_axis.instants[0].echo_units()
    else:
        calendar = ds.time_axis.calendar.as_str()
        units = ds.time_axis.units.echo()

    lines: list[str] = []
    lines.append(f"# calendar={calendar}")
    lines.append(f"# units={units}")
    lines.append("# schema_version=1")
    for k, v in ds.global_attrs.items():
        if k not in ("calendar", "units", "source_format"):
            lines.append(f"# {k}={v}")
    if ds.bounds_axis is not None:
        lines.append(f"# bounds={json.dumps(ds.bounds_axis.encoded_pairs())}")

    ordered_vars = sorted(ds.variables, key=lambda v: v.def_.offset)
    cols = ["time"] + [v.name for v in ordered_vars]
    lines.append(",".join(cols))

    n = len(ds.time_axis.instants)
    for i in range(n):
        t = ds.time_axis.instants[i].encoded_value
        row = [str(t)]
        for v in ordered_vars:
            row.append(str(_read_f64_at(v.bytes, i)))
        lines.append(",".join(row))

    path.write_text("\n".join(lines) + "\n")


def _read_f64_at(bytes_: bytes, idx: int) -> float:
    start = idx * 8
    if start + 8 > len(bytes_):
        return 0.0
    return struct.unpack_from("<d", bytes_, start)[0]


def _f64_vec_to_bytes(vals: list[float]) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)
