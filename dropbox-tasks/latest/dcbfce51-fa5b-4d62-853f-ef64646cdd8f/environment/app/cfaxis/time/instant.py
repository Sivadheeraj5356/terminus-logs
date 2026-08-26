"""Time instant and axis representations."""

from __future__ import annotations

from dataclasses import dataclass

from cfaxis.time.calendar import Calendar
from cfaxis.time.units import UnitsOrigin


@dataclass
class MetadataEcho:
    calendar: str
    units: str


@dataclass
class TimeInstant:
    encoded_value: float
    echo: MetadataEcho

    @classmethod
    def from_encoded(
        cls,
        calendar: Calendar,
        units: UnitsOrigin,
        encoded: float,
    ) -> TimeInstant:
        return cls(
            encoded_value=encoded,
            echo=MetadataEcho(
                calendar=calendar.as_str(),
                units=units.echo(),
            ),
        )

    def sort_key(self, calendar: Calendar, units: UnitsOrigin) -> int:
        y, m, d = calendar.days_from_origin_to_ymd(
            units.origin_year,
            units.origin_month,
            units.origin_day,
            self.encoded_value,
        )
        return calendar.canonical_ordinal(y, m, d)

    def to_encoded_for_write(self, _units: UnitsOrigin) -> float:
        return self.encoded_value

    def echo_calendar(self) -> str:
        return self.echo.calendar

    def echo_units(self) -> str:
        return self.echo.units


@dataclass
class TimeAxis:
    calendar: Calendar
    units: UnitsOrigin
    instants: list[TimeInstant]

    @classmethod
    def from_values(
        cls,
        calendar: Calendar,
        units: UnitsOrigin,
        values: list[float],
    ) -> TimeAxis:
        instants = [
            TimeInstant.from_encoded(calendar, units, v) for v in values
        ]
        return cls(calendar=calendar, units=units, instants=instants)

    def encoded_values(self) -> list[float]:
        return [i.encoded_value for i in self.instants]

    def start_unix(self) -> int:
        if not self.instants:
            return 0
        return self.calendar.encoded_to_unix_seconds_gregorian(
            self.units, self.instants[0].encoded_value
        )

    def end_unix(self) -> int:
        if not self.instants:
            return 0
        return self.calendar.encoded_to_unix_seconds_gregorian(
            self.units, self.instants[-1].encoded_value
        )
