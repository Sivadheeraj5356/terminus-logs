"""Build the climate-axis provenance report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cfaxis.calaxis.axis_types import AxisManifest, MemberPlan, LineageRecord
from cfaxis.formats.common import Dataset


REPORT_FORMAT_VERSION = 1


def _file_digest(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_axis_report(
    *,
    manifest: AxisManifest,
    plan: MemberPlan,
    archive: Dataset,
    archive_path: Path,
    rollup_path: Path,
    lineage: list[LineageRecord],
    recovery_outcome: str,
    conflict: bool,
    committed_generation_id: str | None = None,
) -> dict[str, Any]:
    cal = archive.time_axis.calendar
    units = archive.time_axis.units
    first = None
    last = None
    if archive.time_axis.instants:
        first = list(
            cal.days_from_origin_to_ymd(
                units.origin_year,
                units.origin_month,
                units.origin_day,
                archive.time_axis.instants[0].encoded_value,
            )
        )
        last = list(
            cal.days_from_origin_to_ymd(
                units.origin_year,
                units.origin_month,
                units.origin_day,
                archive.time_axis.instants[-1].encoded_value,
            )
        )

    _ = committed_generation_id
    return {
        "report_format_version": REPORT_FORMAT_VERSION,
        "committed_generation_id": plan.generation_id,
        "run_id": manifest.run_id,
        "archive_path": str(archive_path),
        "archive_digest": _file_digest(archive_path),
        "rollup_path": str(rollup_path),
        "rollup_digest": _file_digest(rollup_path),
        "observation_count": len(archive.time_axis.instants),
        "first_instant": first,
        "last_instant": last,
        "recovery_outcome": recovery_outcome,
        "conflict": conflict,
        "source_lineage": [
            {
                "path": r.path,
                "digest": r.digest,
                "retired": r.retired,
                "observation_count": r.observation_count,
            }
            for r in lineage
        ],
        "planned_remaining": [s.path for s in plan.remaining_sources],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
