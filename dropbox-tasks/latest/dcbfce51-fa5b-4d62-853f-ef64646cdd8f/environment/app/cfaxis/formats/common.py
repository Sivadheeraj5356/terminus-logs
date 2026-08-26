"""Common dataset types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from cfaxis.time import BoundsAxis, Calendar, TimeAxis, UnitsOrigin


class AggKind(str, Enum):
    MEAN = "mean"
    SUM = "sum"
    MIN = "min"
    MAX = "max"


@dataclass
class VariableDef:
    dtype: str
    offset: int
    count: int
    agg: AggKind

    def to_dict(self) -> dict[str, Any]:
        return {
            "dtype": self.dtype,
            "offset": self.offset,
            "count": self.count,
            "agg": self.agg.value,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VariableDef:
        return cls(
            dtype=d["dtype"],
            offset=d["offset"],
            count=d["count"],
            agg=AggKind(d["agg"]),
        )


@dataclass
class VariableData:
    name: str
    def_: VariableDef
    bytes: bytes


@dataclass
class CcfHeader:
    schema_version: int
    calendar: str
    units: str
    time: list[float]
    variables: dict[str, VariableDef]
    bounds: list[list[float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "calendar": self.calendar,
            "units": self.units,
            "time": self.time,
            "variables": {k: v.to_dict() for k, v in sorted(self.variables.items())},
        }
        if self.bounds is not None:
            d["bounds"] = self.bounds
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CcfHeader:
        variables = {
            k: VariableDef.from_dict(v) for k, v in d.get("variables", {}).items()
        }
        return cls(
            schema_version=d["schema_version"],
            calendar=d["calendar"],
            units=d["units"],
            time=d["time"],
            bounds=d.get("bounds"),
            variables=variables,
        )


@dataclass
class Dataset:
    header: CcfHeader
    time_axis: TimeAxis
    bounds_axis: BoundsAxis | None
    variables: list[VariableData]
    global_attrs: dict[str, str] = field(default_factory=dict)

    def calendar(self) -> Calendar:
        return self.time_axis.calendar

    def units(self) -> UnitsOrigin:
        return self.time_axis.units

    def rebuild_axes_from_header(self) -> None:
        cal = Calendar.from_str(self.header.calendar)
        units = UnitsOrigin.parse(self.header.units)
        self.time_axis = TimeAxis.from_values(cal, units, list(self.header.time))
        if self.header.bounds is not None:
            self.bounds_axis = BoundsAxis.from_pairs(cal, units, self.header.bounds)
        else:
            self.bounds_axis = None

    def sync_header_from_axes(self) -> None:
        if self.time_axis.instants:
            self.header.calendar = self.time_axis.instants[0].echo_calendar()
            self.header.units = self.time_axis.instants[0].echo_units()
        else:
            self.header.calendar = self.time_axis.calendar.as_str()
            self.header.units = self.time_axis.units.echo()
        self.header.time = self.time_axis.encoded_values()
        if self.bounds_axis is not None:
            self.header.bounds = self.bounds_axis.encoded_pairs()

    def payload_len(self) -> int:
        return sum(len(v.bytes) for v in self.variables)
