"""Plan which climate members still need calendar-axis incorporation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from cfaxis.calaxis.axis_types import AxisManifest, MemberPlan, SourceEntry
from cfaxis.calaxis.working_state import load_checkpoint, load_lineage


def _content_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_members(manifest: AxisManifest) -> MemberPlan:
    state_dir = Path(manifest.state_dir)
    checkpoint = load_checkpoint(state_dir)
    lineage = load_lineage(state_dir)

    committed_id = (
        checkpoint.committed_generation_id if checkpoint is not None else "none"
    )
    generation_id = f"{manifest.run_id}:{committed_id}:next"

    completed_paths: set[str] = set()
    if checkpoint is not None:
        completed_paths.update(checkpoint.completed_source_paths)
    for rec in lineage:
        if rec.retired:
            completed_paths.add(rec.path)

    remaining: list[SourceEntry] = []
    for src in manifest.sources:
        if src.role == "committed":
            continue
        if src.path in completed_paths:
            continue
        remaining.append(src)

    use_archive = checkpoint is not None and Path(manifest.archive_path).exists()
    return MemberPlan(
        generation_id=generation_id,
        remaining_sources=remaining,
        committed_generation_id=committed_id,
        use_committed_archive=use_archive,
    )


def refresh_source_digests(sources: list[SourceEntry]) -> list[SourceEntry]:
    out: list[SourceEntry] = []
    for src in sources:
        p = Path(src.path)
        digest = _content_digest(p) if p.exists() else src.digest
        out.append(SourceEntry(path=src.path, role=src.role, digest=digest))
    return out
