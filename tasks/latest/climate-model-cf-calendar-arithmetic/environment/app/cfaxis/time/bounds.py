"""Time bounds handling."""

from __future__ import annotations

from dataclasses import dataclass

from cfaxis.time.calendar import Calendar
from cfaxis.time.units import UnitsOrigin


@dataclass
class TimeBounds:
    lower_encoded: float
    upper_encoded: float

    @classmethod
    def from_encoded(
        cls,
        calendar: Calendar,
        units: UnitsOrigin,
        lower: float,
        upper: float,
    ) -> TimeBounds:
        return cls(lower_encoded=lower, upper_encoded=upper)


def normalize_bounds_to_1970_days(
    calendar: Calendar,
    units: UnitsOrigin,
    lower: float,
    upper: float,
) -> tuple[float, float]:
    ly, lm, ld = calendar.days_from_origin_to_ymd(
        units.origin_year,
        units.origin_month,
        units.origin_day,
        lower,
    )
    uy, um, ud = calendar.days_from_origin_to_ymd(
        units.origin_year,
        units.origin_month,
        units.origin_day,
        upper,
    )
    return (
        calendar.date_to_days_since_1970(ly, lm, ld),
        calendar.date_to_days_since_1970(uy, um, ud),
    )


@dataclass
class BoundsAxis:
    calendar: Calendar
    units: UnitsOrigin
    bounds: list[TimeBounds]

    @classmethod
    def from_pairs(
        cls,
        calendar: Calendar,
        units: UnitsOrigin,
        pairs: list[list[float]],
    ) -> BoundsAxis:
        bounds = [
            TimeBounds.from_encoded(calendar, units, lo, hi)
            for lo, hi in pairs
        ]
        return cls(calendar=calendar, units=units, bounds=bounds)

    def encoded_pairs(self) -> list[list[float]]:
        return [[b.lower_encoded, b.upper_encoded] for b in self.bounds]
