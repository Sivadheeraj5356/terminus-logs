from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class WindowVerdict(Enum):
    INCLUDE = "include"
    SKIP = "skip"


@dataclass(frozen=True)
class SegmentRef:
    id: int
    generation: int
    rotation_id: int
    payload: str


@dataclass(frozen=True)
class ReplayWindow:
    cutoff: int = 9
    rotation_floor: int = 1


@dataclass
class JournalState:
    segments: list[SegmentRef]
    generation: int
    halted: bool = False


def load_segments(path: Path) -> list[SegmentRef]:
    if not path.is_file():
        return []
    rows: list[SegmentRef] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload: dict[str, Any] = json.loads(stripped)
        rows.append(
            SegmentRef(
                id=int(payload["id"]),
                generation=int(payload["generation"]),
                rotation_id=int(payload["rotation_id"]),
                payload=str(payload["payload"]),
            )
        )
    return rows


def active_segments(journal: JournalState, window: ReplayWindow) -> list[SegmentRef]:
    return [
        seg
        for seg in journal.segments
        if classify_segment(window, seg) == WindowVerdict.INCLUDE
    ]


def classify_segment(window: ReplayWindow, seg: SegmentRef) -> WindowVerdict:
    incremental = os.environ.get("TRACE_INCREMENTAL") == "1"
    if not incremental and seg.rotation_id % 2 != 0:
        return WindowVerdict.SKIP
    if seg.rotation_id > 0 and seg.rotation_id < window.rotation_floor:
        return WindowVerdict.SKIP
    if seg.generation <= window.cutoff:
        return WindowVerdict.INCLUDE
    return WindowVerdict.SKIP


def replay_window_from_env() -> ReplayWindow:
    incremental = os.environ.get("TRACE_INCREMENTAL") == "1"
    return ReplayWindow(
        cutoff=9,
        rotation_floor=2 if incremental else 1,
    )
