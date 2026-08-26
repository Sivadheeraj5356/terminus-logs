"""Run climate-member calendar-axis incorporation and publish outputs."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from cfaxis.calaxis.manifest import load_manifest
from cfaxis.calaxis.axis_types import (
    Checkpoint,
    JournalEvent,
    LineageRecord,
)
from cfaxis.calaxis.member_plan import plan_members
from cfaxis.calaxis.calendar_merge import merge_datasets
from cfaxis.calaxis.axis_report import build_axis_report, write_report
from cfaxis.calaxis import working_state
from cfaxis.error import ClimError, IncompatibleAppendError, ValidationError
from cfaxis.formats import read_dataset, write_ccf
from cfaxis.formats.io import FormatArg, FreqArg
from cfaxis.resample import bins as resample_bins
from cfaxis.resample import agg as resample_agg
from cfaxis.resample import cache as resample_cache


def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rollup_cache_key(archive_path: Path, ds) -> str:
    hasher = hashlib.sha256()
    hasher.update(str(archive_path).encode())
    hasher.update(str(ds.time_axis.start_unix()).encode())
    hasher.update(str(ds.time_axis.end_unix()).encode())
    hasher.update(ds.header.calendar.encode())
    return hasher.hexdigest()


def _build_monthly(ds, cache_dir: Path, archive_path: Path, use_cache: bool):
    key = _rollup_cache_key(archive_path, ds)
    if use_cache:
        cached = resample_cache.load_cached(cache_dir, key)
        if cached is not None:
            return cached
    assignments = resample_bins.assign_bins(ds, FreqArg.MON)
    monthly = resample_agg.aggregate_bins(ds, assignments, FreqArg.MON)
    if use_cache:
        resample_cache.store_cached(cache_dir, key, monthly)
    return monthly


def run_axis(manifest_path: Path, *, use_cache: bool = True) -> None:
    manifest = load_manifest(manifest_path)
    state_dir = Path(manifest.state_dir)
    archive_path = Path(manifest.archive_path)
    rollup_path = Path(manifest.rollup_path)
    report_path = Path(manifest.report_path)
    cache_dir = Path(manifest.cache_dir)

    plan = plan_members(manifest)
    checkpoint = working_state.load_checkpoint(state_dir)
    lineage = working_state.load_lineage(state_dir)

    base_ds = None
    if plan.use_committed_archive and archive_path.exists():
        base_ds = read_dataset(archive_path, FormatArg.AUTO)

    shards = []
    for src in plan.remaining_sources:
        p = Path(src.path)
        if not p.exists():
            raise ValidationError(f"missing source segment: {src.path}")
        shards.append(read_dataset(p, FormatArg.AUTO))

    try:
        merged = merge_datasets(base_ds, shards)
    except IncompatibleAppendError:
        raise
    except ClimError:
        raise

    stage = working_state.stage_dir(state_dir)
    staged_archive = stage / "archive.ccf"
    staged_rollup = stage / "archive-monthly.ccf"
    staged_report = stage / "climate-axis-report.json"

    write_ccf(staged_archive, merged)
    monthly = _build_monthly(merged, cache_dir, archive_path, use_cache)
    write_ccf(staged_rollup, monthly)

    new_lineage = list(lineage)
    known = {r.path for r in new_lineage}
    for src in plan.remaining_sources:
        dig = _digest_file(Path(src.path))
        n_obs = len(read_dataset(Path(src.path), FormatArg.AUTO).time_axis.instants)
        if src.path in known:
            for rec in new_lineage:
                if rec.path == src.path:
                    rec.digest = dig
                    rec.retired = False
                    rec.observation_count = n_obs
        else:
            new_lineage.append(
                LineageRecord(
                    path=src.path,
                    digest=dig,
                    retired=False,
                    observation_count=n_obs,
                )
            )

    report = build_axis_report(
        manifest=manifest,
        plan=plan,
        archive=merged,
        archive_path=staged_archive,
        rollup_path=staged_rollup,
        lineage=new_lineage,
        recovery_outcome="resumed",
        conflict=False,
    )
    write_report(staged_report, report)

    working_state.append_journal(
        state_dir,
        JournalEvent(event="stage_ready", generation_id=plan.generation_id),
    )

    completed_paths = []
    if checkpoint is not None:
        completed_paths = list(checkpoint.completed_source_paths)
    for src in plan.remaining_sources:
        if src.path not in completed_paths:
            completed_paths.append(src.path)

    new_checkpoint = Checkpoint(
        committed_generation_id=plan.generation_id,
        planned_generation_id=None,
        completed_source_paths=completed_paths,
        archive_path=str(archive_path),
        rollup_path=str(rollup_path),
        report_path=str(report_path),
    )
    working_state.save_checkpoint(state_dir, new_checkpoint)
    working_state.save_lineage(state_dir, new_lineage)
    working_state.append_journal(
        state_dir,
        JournalEvent(event="checkpoint_advanced", generation_id=plan.generation_id),
    )

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged_archive, archive_path)
    shutil.copy2(staged_rollup, rollup_path)
    shutil.copy2(staged_report, report_path)

    working_state.append_journal(
        state_dir,
        JournalEvent(event="published", generation_id=plan.generation_id),
    )

    for p in (staged_archive, staged_rollup, staged_report):
        if p.exists():
            p.unlink()
