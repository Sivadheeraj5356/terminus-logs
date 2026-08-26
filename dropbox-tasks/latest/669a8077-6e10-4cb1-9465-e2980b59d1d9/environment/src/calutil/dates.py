"""Calendar ordinals and environmental monitoring windows."""

from __future__ import annotations


def day_ordinal(date: str) -> int:
    parts = date.split("-")
    if len(parts) != 3:
        raise ValueError(f"invalid date {date}")
    year, month, day = (int(parts[0]), int(parts[1]), int(parts[2]))
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def within_em_window(
    observed: str,
    batch_start: str,
    eval_date: str,
    window_days: int,
) -> bool:
    obs = day_ordinal(observed)
    start = day_ordinal(batch_start)
    end = day_ordinal(eval_date)
    window_start = end - window_days
    return obs > start and obs <= end and obs >= window_start
