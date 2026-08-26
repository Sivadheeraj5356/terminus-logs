"""Dataset validation."""

from __future__ import annotations

from pathlib import Path

from cfaxis.error import ValidationError
from cfaxis.formats import read_dataset
from cfaxis.formats.io import FormatArg
from cfaxis.time import Calendar


def validate_file(path: Path) -> None:
    ds = read_dataset(path, FormatArg.AUTO)

    try:
        Calendar.from_str(ds.header.calendar)
    except Exception as e:
        raise ValidationError(str(e)) from e

    if ds.header.schema_version != 1:
        raise ValidationError(
            f"unsupported schema_version {ds.header.schema_version}"
        )

    if not ds.header.time:
        raise ValidationError("empty time axis")

    for i in range(len(ds.header.time) - 1):
        if ds.header.time[i + 1] <= ds.header.time[i]:
            raise ValidationError("time axis not strictly increasing")

    if ds.header.bounds is not None:
        if len(ds.header.bounds) != len(ds.header.time):
            raise ValidationError("bounds length mismatch")

    for v in ds.variables:
        sz = {"f64": 8, "f32": 4}.get(v.def_.dtype)
        if sz is None:
            raise ValidationError(f"unsupported dtype {v.def_.dtype}")
        if v.def_.count * sz != len(v.bytes):
            raise ValidationError(f"variable {v.name} byte count mismatch")
