"""Deterministic fit-stage isolation checks for the gaa-extract verifier."""

from __future__ import annotations

from pathlib import Path

from tracing import (
    JournalEvent,
    ReadPolicy,
    TESTS_POLICY,
    assert_no_measurement_reads_after_tapeout_seal,
    assert_tapeout_committed_via_temp_rename,
    run_syscall_journal,
)


def verify_atomic_tapeout_replace(
    *,
    cmd: list[str],
    destination: Path,
    env: dict | None = None,
    policy: ReadPolicy = TESTS_POLICY,
) -> tuple[int, list[JournalEvent]]:
    """Run characterize and prove tapeout replacement uses temp-file rename, not polling."""
    completed, events = run_syscall_journal(cmd, env=env, policy=policy)
    assert_tapeout_committed_via_temp_rename(events, destination)
    return completed.returncode, events


def verify_run_keeps_fit_tapeout_only(
    *,
    cmd: list[str],
    tapeout_path: Path,
    data_dir: Path,
    measurement_names: tuple[str, ...],
    env: dict | None = None,
    policy: ReadPolicy = TESTS_POLICY,
) -> tuple[int, list[JournalEvent]]:
    """Run the combined pipeline and forbid post-seal measurement reopens via syscall order."""
    completed, events = run_syscall_journal(cmd, env=env, policy=policy)
    assert_no_measurement_reads_after_tapeout_seal(
        events,
        tapeout_path=tapeout_path,
        data_dir=data_dir,
        measurement_names=measurement_names,
    )
    return completed.returncode, events
