"""Climate-axis incorporation models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceEntry:
    path: str
    role: str = "segment"  # committed | segment
    digest: str | None = None


@dataclass
class LineageRecord:
    path: str
    digest: str
    retired: bool = False
    observation_count: int = 0


@dataclass
class Generation:
    generation_id: str
    archive_digest: str = ""
    rollup_digest: str = ""
    observation_count: int = 0
    first_instant: list[int] | None = None
    last_instant: list[int] | None = None
    source_digests: list[str] = field(default_factory=list)


@dataclass
class Checkpoint:
    committed_generation_id: str
    planned_generation_id: str | None = None
    completed_source_paths: list[str] = field(default_factory=list)
    archive_path: str = "/output/archive.ccf"
    rollup_path: str = "/output/archive-monthly.ccf"
    report_path: str = "/output/climate-axis-report.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "committed_generation_id": self.committed_generation_id,
            "planned_generation_id": self.planned_generation_id,
            "completed_source_paths": list(self.completed_source_paths),
            "archive_path": self.archive_path,
            "rollup_path": self.rollup_path,
            "report_path": self.report_path,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Checkpoint:
        return cls(
            committed_generation_id=d["committed_generation_id"],
            planned_generation_id=d.get("planned_generation_id"),
            completed_source_paths=list(d.get("completed_source_paths", [])),
            archive_path=d.get("archive_path", "/output/archive.ccf"),
            rollup_path=d.get("rollup_path", "/output/archive-monthly.ccf"),
            report_path=d.get("report_path", "/output/climate-axis-report.json"),
        )


@dataclass
class JournalEvent:
    event: str
    generation_id: str
    detail: str = ""


@dataclass
class AxisManifest:
    schema_version: int
    calendar: str
    units: str
    sources: list[SourceEntry]
    state_dir: str
    archive_path: str
    rollup_path: str
    report_path: str
    run_id: str = "default"
    cache_dir: str = "/var/lib/climconvert/cache"


@dataclass
class MemberPlan:
    generation_id: str
    remaining_sources: list[SourceEntry]
    committed_generation_id: str
    use_committed_archive: bool
