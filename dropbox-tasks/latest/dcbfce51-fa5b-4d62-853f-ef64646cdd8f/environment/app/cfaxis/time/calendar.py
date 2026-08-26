"""Calendar arithmetic for climate time coordinates."""

from __future__ import annotations

from enum import Enum

from cfaxis.error import UnsupportedCalendarError


class Calendar(str, Enum):
    GREGORIAN = "gregorian"
    PROLEPTIC_GREGORIAN = "proleptic_gregorian"
    NOLEAP = "noleap"
    DAY360 = "360_day"

    def as_str(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, s: str) -> Calendar:
        try:
            return cls(s)
        except ValueError:
            raise UnsupportedCalendarError(s) from None

    def days_in_month(self, year: int, month: int) -> int:
        if self is Calendar.DAY360:
            return 30
        if self is Calendar.NOLEAP:
            if month in (1, 3, 5, 7, 8, 10, 12):
                return 31
            if month in (4, 6, 9, 11):
                return 30
            if month == 2:
                return 28
            return 30
        if month in (1, 3, 5, 7, 8, 10, 12):
            return 31
        if month in (4, 6, 9, 11):
            return 30
        if month == 2:
            return 29 if self._is_leap_gregorian(year) else 28
        return 30

    def days_in_year(self, year: int) -> int:
        if self is Calendar.DAY360:
            return 360
        if self is Calendar.NOLEAP:
            return 365
        return 366 if self._is_leap_gregorian(year) else 365

    @staticmethod
    def _is_leap_gregorian(year: int) -> bool:
        return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

    def date_to_days_since_1970(self, year: int, month: int, day: int) -> float:
        days = 0
        for y in range(1970, year):
            days += self.days_in_year(y)
        for m in range(1, month):
            days += self.days_in_month(year, m)
        days += day - 1
        return float(days)

    def days_from_origin_to_ymd(
        self,
        origin_year: int,
        origin_month: int,
        origin_day: int,
        encoded_days: float,
    ) -> tuple[int, int, int]:
        whole = int(encoded_days // 1)
        year = origin_year
        month = origin_month
        day = origin_day
        remaining = whole

        while remaining > 0:
            dim = self.days_in_month(year, month)
            days_left_in_month = dim - day + 1
            if remaining < days_left_in_month:
                day += remaining
                remaining = 0
            else:
                remaining -= days_left_in_month
                day = 1
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1

        while remaining < 0:
            if day > 1:
                step = min(day - 1, -remaining)
                day -= step
                remaining += step
            elif month > 1:
                month -= 1
                day = self.days_in_month(year, month)
                remaining += 1
            else:
                year -= 1
                month = 12
                day = self.days_in_month(year, month)
                remaining += 1

        return year, month, day

    def ymd_to_encoded_days(
        self,
        origin: object,
        year: int,
        month: int,
        day: int,
    ) -> float:
        oy, om, od = origin.origin_ymd()  # type: ignore[attr-defined]
        origin_ord = self.canonical_ordinal(oy, om, od)
        target_ord = self.canonical_ordinal(year, month, day)
        return float(target_ord - origin_ord)

    def canonical_ordinal(self, year: int, month: int, day: int) -> int:
        ord_ = 0
        for y in range(0, year):
            ord_ += self.days_in_year(y)
        for m in range(1, month):
            ord_ += self.days_in_month(year, m)
        ord_ += day - 1
        return ord_

    def encoded_to_unix_seconds_gregorian(
        self,
        origin: object,
        encoded: float,
    ) -> int:
        y, m, d = self.days_from_origin_to_ymd(
            origin.origin_year,  # type: ignore[attr-defined]
            origin.origin_month,  # type: ignore[attr-defined]
            origin.origin_day,  # type: ignore[attr-defined]
            encoded,
        )
        days = self.date_to_days_since_1970(y, m, d)
        return round(days * 86400.0)
