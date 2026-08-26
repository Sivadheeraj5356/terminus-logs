"""CCF binary format."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from cfaxis.error import FormatError
from cfaxis.formats.common import (
    CcfHeader,
    Dataset,
    VariableData,
)
from cfaxis.time import BoundsAxis, Calendar, TimeAxis, UnitsOrigin

MAGIC = b"CCF1"


def _dtype_size(dtype: str) -> int:
    if dtype == "f64":
        return 8
    if dtype == "f32":
        return 4
    raise FormatError(f"unsupported dtype {dtype}")


def read_ccf(path: Path) -> Dataset:
    data = path.read_bytes()
    if len(data) < 8 or data[:4] != MAGIC:
        raise FormatError("invalid CCF magic")
    (json_len,) = struct.unpack_from("<I", data, 4)
    json_buf = data[8 : 8 + json_len]
    header = CcfHeader.from_dict(json.loads(json_buf.decode("utf-8")))
    payload = data[8 + json_len :]

    cal = Calendar.from_str(header.calendar)
    units = UnitsOrigin.parse(header.units)
    time_axis = TimeAxis.from_values(cal, units, list(header.time))
    bounds_axis = None
    if header.bounds is not None:
        bounds_axis = BoundsAxis.from_pairs(cal, units, header.bounds)

    variables: list[VariableData] = []
    for name, def_ in header.variables.items():
        start = def_.offset
        end = start + def_.count * _dtype_size(def_.dtype)
        if end > len(payload):
            raise FormatError(f"variable {name} extends past payload")
        variables.append(
            VariableData(name=name, def_=def_, bytes=payload[start:end])
        )

    global_attrs = {"source_format": "ccf"}

    return Dataset(
        header=header,
        time_axis=time_axis,
        bounds_axis=bounds_axis,
        variables=variables,
        global_attrs=global_attrs,
    )


def write_ccf_payload(ds: Dataset) -> bytes:
    max_end = 0
    for v in ds.variables:
        sz = _dtype_size(v.def_.dtype)
        max_end = max(max_end, v.def_.offset + v.def_.count * sz)
    payload = bytearray(max_end)
    for v in ds.variables:
        sz = _dtype_size(v.def_.dtype)
        end = v.def_.offset + v.def_.count * sz
        payload[v.def_.offset : end] = v.bytes
    return bytes(payload)


def write_ccf(path: Path, ds: Dataset) -> None:
    header = CcfHeader(
        schema_version=ds.header.schema_version,
        calendar=ds.header.calendar,
        units=ds.header.units,
        time=list(ds.header.time),
        bounds=ds.header.bounds,
        variables=dict(ds.header.variables),
    )
    if ds.time_axis.instants:
        header.calendar = ds.time_axis.instants[0].echo_calendar()
        header.units = ds.time_axis.instants[0].echo_units()
    header.time = ds.time_axis.encoded_values()
    if ds.bounds_axis is not None:
        header.bounds = ds.bounds_axis.encoded_pairs()

    json_bytes = json.dumps(header.to_dict(), separators=(",", ":")).encode("utf-8")
    payload = write_ccf_payload(ds)

    with path.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<I", len(json_bytes)))
        f.write(json_bytes)
        f.write(payload)
