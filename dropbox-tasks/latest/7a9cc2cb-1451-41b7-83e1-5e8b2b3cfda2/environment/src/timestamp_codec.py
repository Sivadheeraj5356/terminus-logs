"""Timestamp normalization and ordering comparisons."""

from datetime import datetime, timezone


def to_epoch_seconds(timestamp):
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    if isinstance(timestamp, str):
        text = timestamp.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.timestamp()
    raise ValueError(f"Unsupported timestamp type: {type(timestamp)}")


def timestamps_in_order(previous, current):
    if previous is None:
        return True
    try:
        return to_epoch_seconds(current) >= to_epoch_seconds(previous)
    except ValueError:
        return str(current) >= str(previous)
