"""CF units string parsing."""

from __future__ import annotations

from dataclasses import dataclass

from cfaxis.error import ParseError
from cfaxis.time.calendar import Calendar


@dataclass
class UnitsOrigin:
    unit_name: str
    origin_year: int
    origin_month: int
    origin_day: int
    origin_hour: int
    origin_minute: int
    origin_second: int
    echo_string: str

    @classmethod
    def parse(cls, s: str) -> UnitsOrigin:
        s = s.strip()
        parts = s.split(" ", 2)
        if len(parts) < 3 or parts[0] != "days" or parts[1] != "since":
            raise ParseError(f"invalid units: {s}")
        datetime_part = parts[2]
        if " " in datetime_part:
            date_part, time_part = datetime_part.split(" ", 1)
        else:
            date_part, time_part = datetime_part, "00:00:00"
        date_bits = date_part.split("-")
        if len(date_bits) != 3:
            raise ParseError(f"invalid date in units: {s}")
        time_bits = time_part.split(":")
        if len(time_bits) != 3:
            raise ParseError(f"invalid time in units: {s}")
        try:
            return cls(
                unit_name="days",
                origin_year=int(date_bits[0]),
                origin_month=int(date_bits[1]),
                origin_day=int(date_bits[2]),
                origin_hour=int(time_bits[0]),
                origin_minute=int(time_bits[1]),
                origin_second=int(time_bits[2]),
                echo_string=s,
            )
        except ValueError:
            raise ParseError(s) from None

    def origin_ymd(self) -> tuple[int, int, int]:
        return self.origin_year, self.origin_month, self.origin_day

    def echo(self) -> str:
        return self.echo_string

    def days_since_1970_origin(self) -> float:
        cal = Calendar.GREGORIAN
        y, m, d = self.origin_ymd()
        return cal.date_to_days_since_1970(y, m, d)
