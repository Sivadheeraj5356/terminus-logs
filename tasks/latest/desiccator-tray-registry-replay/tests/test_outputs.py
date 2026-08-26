"""Verifier tests for desiccator tray replay."""

from __future__ import annotations

import json
import shutil
import subprocess

from conftest import (
    BIN,
    EXAMPLE_BAD_UNITS,
    EXAMPLE_CR,
    EXAMPLE_DUP,
    EXAMPLE_EMPTY_TRAY,
    EXAMPLE_LOCKED,
    EXAMPLE_HELD,
    EXAMPLE_UNDERFLOW,
    EXAMPLE_REGEN,
    EXAMPLE_RETRY,
    EXAMPLE_TAB,
    OUT,
    PRESERVED,
    SEED,
    assert_quiet_success,
    canonical_raw,
    load_registry,
    run_tray,
    write_preserved,
    write_task,
)
from scenario_helpers import copy_task

ONE_TRAY = [{"tray_id": "main", "capacity_units": 5, "tier": 1, "regen_every": 3}]


def _reason_for(rep: dict, event_id: str) -> str | None:
    row = next((r for r in rep["rejected_events"] if r["event_id"] == event_id), None)
    return row["reason"] if row else None


def test_binary_is_native_elf() -> None:
    """The installed command is the compiled Rust binary: a native ELF executable."""
    run_tray(SEED)
    assert BIN.is_file()
    proc = subprocess.run(["file", str(BIN)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert "ELF" in proc.stdout
    assert "executable" in proc.stdout.lower()


def test_empty_event_id_is_bad_event(tmp_path) -> None:
    """An empty event_id rejects BAD_EVENT before any other check and changes no state."""
    root = write_task(
        tmp_path / "bad_event",
        ONE_TRAY,
        [("", "LOAD", "main", "2")],
    )
    run_tray(root)
    rep = load_registry()
    bad = next(r for r in rep["rejected_events"] if r["reason"] == "BAD_EVENT")
    assert bad["event_id"] == ""
    assert rep["summary"]["rejected_events"] == 1
    assert rep["summary"]["applied_events"] == 0
    assert rep["trays"][0]["units"] == 0


def test_seal_bad_state_on_empty_tray(tmp_path) -> None:
    """SEAL on a tray with zero units rejects BAD_STATE and leaves it unsealed."""
    root = write_task(
        tmp_path / "seal_empty",
        ONE_TRAY,
        [("s1", "SEAL", "main")],
    )
    run_tray(root)
    rep = load_registry()
    assert _reason_for(rep, "s1") == "BAD_STATE"
    assert rep["trays"][0]["sealed"] is False


def test_seal_bad_state_when_already_sealed(tmp_path) -> None:
    """A second SEAL on an already-sealed tray rejects BAD_STATE; the tray stays sealed."""
    root = write_task(
        tmp_path / "seal_twice",
        ONE_TRAY,
        [("l1", "LOAD", "main", "3"), ("s1", "SEAL", "main"), ("s2", "SEAL", "main")],
    )
    run_tray(root)
    rep = load_registry()
    assert _reason_for(rep, "s2") == "BAD_STATE"
    assert _reason_for(rep, "s1") is None
    assert rep["trays"][0]["sealed"] is True


def test_open_bad_state_when_not_sealed(tmp_path) -> None:
    """OPEN on a tray that is not sealed rejects BAD_STATE."""
    root = write_task(
        tmp_path / "open_unsealed",
        ONE_TRAY,
        [("l1", "LOAD", "main", "2"), ("o1", "OPEN", "main")],
    )
    run_tray(root)
    rep = load_registry()
    assert _reason_for(rep, "o1") == "BAD_STATE"
    assert rep["trays"][0]["sealed"] is False


def test_tray_locked_blocks_every_op_except_lock_unlock(tmp_path) -> None:
    """While locked, every affected op rejects TRAY_LOCKED; only LOCK and UNLOCK apply."""
    root = write_task(
        tmp_path / "locked_all_ops",
        ONE_TRAY,
        [
            ("k1", "LOCK", "main"),
            ("a1", "LOAD", "main", "2"),
            ("a2", "UNLOAD", "main", "1"),
            ("a3", "REGEN", "main"),
            ("a4", "SEAL", "main"),
            ("a5", "OPEN", "main"),
            ("a6", "HOLD", "main"),
            ("a7", "RELEASE", "main"),
            ("k2", "UNLOCK", "main"),
        ],
    )
    run_tray(root)
    rep = load_registry()
    blocked = {"a1", "a2", "a3", "a4", "a5", "a6", "a7"}
    locked_ids = {r["event_id"] for r in rep["rejected_events"] if r["reason"] == "TRAY_LOCKED"}
    assert blocked.issubset(locked_ids)
    assert [r["reason"] for r in rep["rejected_events"]].count("TRAY_LOCKED") == len(blocked)
    # LOCK and UNLOCK applied and were never rejected.
    assert _reason_for(rep, "k1") is None
    assert _reason_for(rep, "k2") is None
    tray = rep["trays"][0]
    assert tray["locked"] is False
    assert tray["units"] == 0
    assert tray["sealed"] is False
    assert rep["summary"]["applied_events"] == 2


def test_seed_run_success_is_quiet() -> None:
    """Seed fixture run exits zero with empty stdout/stderr."""
    code, out, err = run_tray(SEED)
    assert_quiet_success(code, out, err)


def test_zero_args_defaults_to_app_task_file() -> None:
    """Zero CLI arguments default to /app/task_file and match an explicit seed path call."""
    if OUT.exists():
        OUT.unlink()
    proc = subprocess.run([str(BIN)], capture_output=True, text=True, timeout=120, check=False)
    assert_quiet_success(proc.returncode, proc.stdout, proc.stderr)
    default_raw = canonical_raw()

    if OUT.exists():
        OUT.unlink()
    code, out, err = run_tray(SEED)
    assert_quiet_success(code, out, err)
    explicit_raw = canonical_raw()

    assert default_raw == explicit_raw


def test_output_file_exists_after_seed() -> None:
    """Successful seed run writes registry.json."""
    run_tray(SEED)
    assert OUT.is_file()


def test_top_level_keys_and_summary() -> None:
    """Report includes required top-level keys and exact seed summary counts."""
    run_tray(SEED)
    rep = load_registry()
    assert set(rep) == {
        "duplicate_events",
        "invalid_lines",
        "rejected_events",
        "summary",
        "trays",
    }
    summary = rep["summary"]
    assert list(summary.keys()) == sorted(summary.keys())
    for key in (
        "applied_events",
        "duplicate_events",
        "invalid_lines",
        "loads_applied",
        "rejected_events",
        "total_lines",
        "unloads_applied",
    ):
        assert key in summary
    assert summary["total_lines"] == 14
    assert summary["applied_events"] == 12
    assert summary["rejected_events"] == 2
    assert summary["duplicate_events"] == 0
    assert summary["invalid_lines"] == 0
    assert summary["loads_applied"] == 4
    assert summary["unloads_applied"] == 2


def test_trays_sorted_with_live_state() -> None:
    """Trays are sorted lexicographically with live registry fields."""
    run_tray(SEED)
    rep = load_registry()
    names = [t["tray_id"] for t in rep["trays"]]
    assert names == sorted(names)
    alpha = next(t for t in rep["trays"] if t["tray_id"] == "alpha")
    assert alpha["units"] == 4
    assert alpha["sealed"] is False
    assert alpha["cycles_since_regen"] == 2
    beta = next(t for t in rep["trays"] if t["tray_id"] == "beta")
    assert beta["units"] == 4
    gamma = next(t for t in rep["trays"] if t["tray_id"] == "gamma")
    assert gamma["units"] == 1


def test_json_canonical_indent_and_sort() -> None:
    """Output uses two-space indent, sorted keys, trailing newline."""
    run_tray(SEED)
    raw = canonical_raw()
    assert raw.endswith("\n")
    rep = json.loads(raw)
    expected = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    assert raw == expected


def test_unknown_op_rejected_on_seed() -> None:
    """Unknown operations appear in rejected_events on the seed tree."""
    run_tray(SEED)
    rep = load_registry()
    unk = next(r for r in rep["rejected_events"] if r["reason"] == "UNKNOWN_OP")
    assert unk["event_id"] == "d011"
    assert unk["ordinal"] == 10


def test_tray_locked_rejected_on_seed() -> None:
    """LOAD while locked rejects with TRAY_LOCKED on the seed tree."""
    run_tray(SEED)
    rep = load_registry()
    locked = next(r for r in rep["rejected_events"] if r["reason"] == "TRAY_LOCKED")
    assert locked["event_id"] == "d009"
    assert locked["ordinal"] == 8


def test_fatal_bad_arity_preserves_output() -> None:
    """Two CLI args is fatal and preserves existing registry.json bytes."""
    write_preserved()
    proc = subprocess.run([str(BIN), "/app/task_file", "extra"], capture_output=True, text=True, check=False)
    assert proc.returncode == 1
    assert OUT.read_text(encoding="utf-8") == PRESERVED


def test_fatal_missing_events_dir() -> None:
    """Missing events directory is a silent fatal."""
    tmp = copy_task(SEED)
    shutil.rmtree(tmp / "events")
    code, _, _ = run_tray(tmp, clear_output=False)
    assert code == 1


def test_fatal_missing_trays_json() -> None:
    """Missing trays.json is a silent fatal."""
    tmp = copy_task(SEED)
    (tmp / "trays.json").unlink()
    code, _, _ = run_tray(tmp, clear_output=False)
    assert code == 1


def test_fatal_missing_trays_json_preserves_output() -> None:
    """Missing trays.json leaves existing registry.json bytes untouched."""
    write_preserved()
    tmp = copy_task(SEED)
    (tmp / "trays.json").unlink()
    proc = subprocess.run([str(BIN), str(tmp)], capture_output=True, text=True, check=False)
    assert proc.returncode == 1
    assert OUT.read_text(encoding="utf-8") == PRESERVED


def test_fatal_no_tray_shards() -> None:
    """An events tree with no .tray files is a silent fatal."""
    tmp = copy_task(SEED)
    for path in list((tmp / "events").rglob("*.tray")):
        path.unlink()
    code, _, _ = run_tray(tmp, clear_output=False)
    assert code == 1


def test_fatal_invalid_trays_json_shape() -> None:
    """Malformed trays.json is a silent fatal."""
    tmp = copy_task(SEED)
    (tmp / "trays.json").write_text("{}", encoding="utf-8")
    code, _, _ = run_tray(tmp, clear_output=False)
    assert code == 1


def test_fatal_invalid_utf8_shard() -> None:
    """Invalid UTF-8 in a .tray shard is a silent fatal."""
    tmp = copy_task(SEED)
    for path in list((tmp / "events").rglob("*.tray")):
        path.unlink()
    bad = tmp / "events" / "only.tray"
    bad.write_bytes(b"\xff\xfe\n")
    code, _, _ = run_tray(tmp, clear_output=False)
    assert code == 1


def test_fatal_invalid_utf8_shard_preserves_output() -> None:
    """Invalid UTF-8 in a shard leaves existing registry.json bytes untouched."""
    write_preserved()
    tmp = copy_task(SEED)
    for path in list((tmp / "events").rglob("*.tray")):
        path.unlink()
    (tmp / "events" / "only.tray").write_bytes(b"\xff\xfe\n")
    proc = subprocess.run([str(BIN), str(tmp)], capture_output=True, text=True, check=False)
    assert proc.returncode == 1
    assert OUT.read_text(encoding="utf-8") == PRESERVED


def test_locked_scope_example() -> None:
    """TRAY_LOCKED blocks LOAD but LOCK and UNLOCK still apply while locked."""
    run_tray(EXAMPLE_LOCKED)
    rep = load_registry()
    reasons = [r["reason"] for r in rep["rejected_events"]]
    assert reasons.count("TRAY_LOCKED") == 1
    locked = next(r for r in rep["rejected_events"] if r["reason"] == "TRAY_LOCKED")
    assert locked["event_id"] == "l002"
    st = rep["trays"][0]
    assert st["locked"] is False
    assert st["units"] == 1


def test_held_scope_example() -> None:
    """TRAY_HELD blocks LOAD, UNLOAD, REGEN, SEAL, and OPEN but not LOCK, UNLOCK, or RELEASE."""
    run_tray(EXAMPLE_HELD)
    rep = load_registry()
    reasons = [r["reason"] for r in rep["rejected_events"]]
    assert reasons.count("TRAY_HELD") >= 5
    held_ops = {r["event_id"] for r in rep["rejected_events"] if r["reason"] == "TRAY_HELD"}
    assert {"h003", "h004", "h005", "h006", "h007"}.issubset(held_ops)
    open_rej = next(r for r in rep["rejected_events"] if r["event_id"] == "h007")
    assert open_rej["reason"] == "TRAY_HELD"
    st = rep["trays"][0]
    assert st["held"] is False
    assert st["units"] == 3


def test_bad_units_example() -> None:
    """Non-numeric LOAD units reject with BAD_UNITS."""
    run_tray(EXAMPLE_BAD_UNITS)
    rep = load_registry()
    bad = next(r for r in rep["rejected_events"] if r["reason"] == "BAD_UNITS")
    assert bad["event_id"] == "b001"
    assert rep["trays"][0]["units"] == 0


def test_empty_tray_example() -> None:
    """UNLOAD on an empty tray rejects with EMPTY_TRAY."""
    run_tray(EXAMPLE_EMPTY_TRAY)
    rep = load_registry()
    empty = next(r for r in rep["rejected_events"] if r["reason"] == "EMPTY_TRAY")
    assert empty["event_id"] == "e001"
    assert rep["trays"][0]["units"] == 0


def test_underflow_example() -> None:
    """UNLOAD exceeding current units rejects with UNDERFLOW without changing state."""
    run_tray(EXAMPLE_UNDERFLOW)
    rep = load_registry()
    under = next(r for r in rep["rejected_events"] if r["reason"] == "UNDERFLOW")
    assert under["event_id"] == "f002"
    assert rep["trays"][0]["units"] == 3


def test_regen_blocked_distant_lower_tier() -> None:
    """REGEN rejects when any lower tier holds units, not only the adjacent tier."""
    run_tray(EXAMPLE_REGEN)
    rep = load_registry()
    assert any(r["reason"] == "REGEN_BLOCKED" for r in rep["rejected_events"])
    gamma = next(t for t in rep["trays"] if t["tray_id"] == "gamma")
    assert gamma["units"] == 2


def test_reject_retry_example() -> None:
    """OVER_CAPACITY reject does not consume event_id; a later load succeeds."""
    run_tray(EXAMPLE_RETRY)
    rep = load_registry()
    st = rep["trays"][0]
    assert st["units"] == 4
    over = [r for r in rep["rejected_events"] if r["reason"] == "OVER_CAPACITY"]
    assert len(over) == 1
    assert over[0]["event_id"] == "h001"


def test_duplicate_retry_example() -> None:
    """Rejected OVER_CAPACITY with event_id d001 does not block a later d001 retry."""
    run_tray(EXAMPLE_DUP)
    rep = load_registry()
    st = rep["trays"][0]
    assert st["units"] == 4
    assert rep["summary"]["duplicate_events"] == 0
    over = [r for r in rep["rejected_events"] if r["reason"] == "OVER_CAPACITY"]
    assert len(over) == 1
    assert over[0]["event_id"] == "d001"


def test_bad_line_trailing_tab_example() -> None:
    """Trailing empty tab column yields invalid_lines entry."""
    run_tray(EXAMPLE_TAB)
    rep = load_registry()
    assert rep["invalid_lines"]
    assert rep["summary"]["invalid_lines"] >= 1


def test_cr_only_bare_cr_line_endings() -> None:
    """Bare CR separators replay LOAD then UNLOAD in one shard."""
    run_tray(EXAMPLE_CR)
    rep = load_registry()
    st = rep["trays"][0]
    assert st["units"] == 1
    assert rep["summary"]["total_lines"] == 2
    assert rep["summary"]["loads_applied"] == 1
    assert rep["summary"]["unloads_applied"] == 1


def test_replay_path_tie_break_by_relative_path(tmp_path) -> None:
    """Lexicographic shard path order decides which LOAD hits OVER_CAPACITY."""
    root = tmp_path / "tie_task"
    (root / "events" / "aa").mkdir(parents=True)
    (root / "events" / "ab").mkdir(parents=True)
    (root / "trays.json").write_text(
        json.dumps({"trays": [{"tray_id": "main", "capacity_units": 5, "tier": 1, "regen_every": 3}]}),
        encoding="utf-8",
    )
    (root / "events" / "aa" / "first.tray").write_text("e2\tLOAD\tmain\t3\t\n", encoding="utf-8")
    (root / "events" / "ab" / "second.tray").write_text("e1\tLOAD\tmain\t3\t\n", encoding="utf-8")
    run_tray(root)
    rep = load_registry()
    over = next(r for r in rep["rejected_events"] if r["reason"] == "OVER_CAPACITY")
    assert over["event_id"] == "e1"
    tray = rep["trays"][0]
    assert tray["units"] == 3


def test_output_dir_recreated_removes_stale() -> None:
    """Successful run deletes and recreates /app/output, removing stale files."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    stale = OUT.parent / "stale.txt"
    stale.write_text("old", encoding="utf-8")
    run_tray(SEED)
    assert OUT.is_file()
    assert not stale.exists()


def test_rejected_events_include_source_and_line() -> None:
    """Rejected events carry sorted keys, discovery ordinal, absolute source path, and line number."""
    run_tray(SEED)
    rep = load_registry()
    locked = next(r for r in rep["rejected_events"] if r["reason"] == "TRAY_LOCKED")
    assert list(locked.keys()) == sorted(locked.keys())
    assert locked["ordinal"] == 8
    assert locked["line"] == 4
    assert locked["event_id"] == "d009"
    assert "/beta/02_more.tray" in locked["source"]


def test_tmp_copy_accepted() -> None:
    """Single-arg mode accepts copied task roots under /tmp."""
    tmp = copy_task(SEED)
    code, out, err = run_tray(tmp)
    assert_quiet_success(code, out, err)
    assert OUT.is_file()
