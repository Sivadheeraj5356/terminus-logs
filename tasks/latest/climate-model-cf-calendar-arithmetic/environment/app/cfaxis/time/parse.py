"""Time value parsing."""

from cfaxis.error import ParseError


def parse_time_value(s: str) -> float:
    try:
        return float(s.strip())
    except ValueError as e:
        raise ParseError(f"time value '{s}': {e}") from e
