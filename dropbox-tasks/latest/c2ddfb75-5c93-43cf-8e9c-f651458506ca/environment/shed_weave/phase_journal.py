from __future__ import annotations

from pathlib import Path

from shed_weave.compile_window import (
    JournalState,
    ReplayWindow,
    SegmentRef,
    active_segments,
    load_segments,
    replay_window_from_env,
)


def fixtures_root(env_root: Path) -> Path:
    return env_root / "fixtures"


def rotation_segment_path(env_root: Path) -> Path:
    return fixtures_root(env_root) / "rotation-segment" / "segments.jsonl"


def hydrate_journal(env_root: Path, profile: str, resume: bool) -> JournalState:
    segments = load_segments(rotation_segment_path(env_root))
    if not segments:
        segments = [
            SegmentRef(id=1, generation=1, rotation_id=0, payload=profile),
        ]
    generation = max(seg.generation for seg in segments)
    return JournalState(segments=segments, generation=generation, halted=False)


def replay_floor_for_window(journal: JournalState, window: ReplayWindow) -> int:
    active = active_segments(journal, window)
    if not active:
        return 0
    return min(seg.generation for seg in active)


def resolve_replay_floor(env_root: Path, profile: str) -> int:
    journal = hydrate_journal(env_root, profile, resume=False)
    window = replay_window_from_env()
    return replay_floor_for_window(journal, window)
