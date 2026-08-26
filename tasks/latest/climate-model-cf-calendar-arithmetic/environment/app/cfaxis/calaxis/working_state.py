"""Persistent climate-axis working state."""

from __future__ import annotations

import json
from pathlib import Path

from cfaxis.calaxis.axis_types import Checkpoint, JournalEvent, LineageRecord
from cfaxis.error import FormatError


def state_paths(state_dir: Path) -> dict[str, Path]:
    return {
        "checkpoint": state_dir / "checkpoint.json",
        "journal": state_dir / "journal.jsonl",
        "lineage": state_dir / "lineage.json",
        "stage": state_dir / "stage",
    }


def load_checkpoint(state_dir: Path) -> Checkpoint | None:
    path = state_paths(state_dir)["checkpoint"]
    if not path.exists():
        return None
    return Checkpoint.from_dict(json.loads(path.read_text()))


def save_checkpoint(state_dir: Path, checkpoint: Checkpoint) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_paths(state_dir)["checkpoint"]
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def load_lineage(state_dir: Path) -> list[LineageRecord]:
    path = state_paths(state_dir)["lineage"]
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [
        LineageRecord(
            path=r["path"],
            digest=r["digest"],
            retired=bool(r.get("retired", False)),
            observation_count=int(r.get("observation_count", 0)),
        )
        for r in data.get("records", [])
    ]


def save_lineage(state_dir: Path, records: list[LineageRecord]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_paths(state_dir)["lineage"]
    payload = {
        "records": [
            {
                "path": r.path,
                "digest": r.digest,
                "retired": r.retired,
                "observation_count": r.observation_count,
            }
            for r in records
        ]
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def append_journal(state_dir: Path, event: JournalEvent) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_paths(state_dir)["journal"]
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "event": event.event,
                    "generation_id": event.generation_id,
                    "detail": event.detail,
                },
                sort_keys=True,
            )
            + "\n"
        )


def read_journal(state_dir: Path) -> list[JournalEvent]:
    path = state_paths(state_dir)["journal"]
    if not path.exists():
        return []
    events: list[JournalEvent] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        events.append(
            JournalEvent(
                event=d["event"],
                generation_id=d["generation_id"],
                detail=d.get("detail", ""),
            )
        )
    return events


def stage_dir(state_dir: Path) -> Path:
    path = state_paths(state_dir)["stage"]
    path.mkdir(parents=True, exist_ok=True)
    return path


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FormatError(f"missing {label}: {path}")
