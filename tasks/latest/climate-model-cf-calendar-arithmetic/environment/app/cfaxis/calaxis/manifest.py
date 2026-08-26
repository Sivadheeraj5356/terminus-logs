"""Parse the climate-axis incorporation manifest."""

from __future__ import annotations

import tomllib
from pathlib import Path

from cfaxis.calaxis.axis_types import AxisManifest, SourceEntry
from cfaxis.error import TomlError, ValidationError


def load_manifest(path: Path) -> AxisManifest:
    try:
        data = tomllib.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001
        raise TomlError(f"invalid compaction manifest: {exc}") from exc

    schema = int(data.get("schema_version", 0))
    if schema != 1:
        raise ValidationError(f"unsupported compaction schema_version {schema}")

    sources = [
        SourceEntry(
            path=str(s["path"]),
            role=str(s.get("role", "segment")),
            digest=s.get("digest"),
        )
        for s in data.get("sources", [])
    ]
    if not sources:
        raise ValidationError("compaction manifest has no sources")

    return AxisManifest(
        schema_version=schema,
        calendar=str(data["calendar"]),
        units=str(data["units"]),
        sources=sources,
        state_dir=str(data.get("state_dir", "/var/lib/climconvert/climate_axis")),
        archive_path=str(data.get("archive_path", "/output/archive.ccf")),
        rollup_path=str(data.get("rollup_path", "/output/archive-monthly.ccf")),
        report_path=str(data.get("report_path", "/output/climate-axis-report.json")),
        run_id=str(data.get("run_id", "default")),
        cache_dir=str(data.get("cache_dir", "/var/lib/climconvert/cache")),
    )
