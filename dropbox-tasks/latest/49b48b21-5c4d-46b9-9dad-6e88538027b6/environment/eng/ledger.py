from __future__ import annotations

from pathlib import Path

from .io_util import read_jsonl


def load_ledger(path: str) -> list[dict[str, object]]:
    return read_jsonl(Path(path))


def filter_generation(events: list[dict[str, object]], floor: int) -> list[dict[str, object]]:
    return [event for event in events if int(event["gen"]) > int(floor)]
