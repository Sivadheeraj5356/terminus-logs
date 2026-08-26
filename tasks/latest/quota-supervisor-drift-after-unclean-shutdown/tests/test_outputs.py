"""Verifier for recovery run records, list probes, and ledger alignment."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ENV = Path("/app/environment")
FIXTURE_ROOT = Path("/tests/fixtures/data")
CTL = "/app/bin/ctl_s8"
CLIENT = "/app/bin/client_t4"
RUN = Path("/app/output/recovery_run.json")
FINGERPRINT = Path("/app/output/state_fingerprint.txt")
LEDGER = ENV / "data" / "q9" / "rows_q2.json"
M9 = ENV / "data" / "m9"
J4 = ENV / "data" / "j4"
MATRIX_M01 = ENV / "data" / "matrix" / "m01_lane.json"
MATRIX_M02 = ENV / "data" / "matrix" / "m02_lane.json"
FIXTURES = ("c01", "c02", "c03", "c04")


@dataclass
class StreamSeg:
    segment_id: str
    era: int
    attach_id: str
    kind: str
    ok: bool


def _entry_hash(entries: list[dict]) -> str:
    slim = [
        {
            "run_label": ev["run_label"],
            "phase": ev["phase"],
            "segment_id": ev["segment_id"],
            "era": ev["era"],
            "attach_id": ev["attach_id"],
            "outcome": ev["outcome"],
        }
        for ev in entries
    ]
    slim.sort(key=lambda r: (r["run_label"], r["segment_id"], r["phase"]))
    raw = json.dumps(slim, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _restore_data_fixtures() -> None:
    """Reset mutable data trees from shipped verifier fixtures."""
    for name in ("q9", "m9", "j4", "k7"):
        dst = ENV / "data" / name
        src = FIXTURE_ROOT / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def _purge_outputs() -> None:
    for path in (RUN, FINGERPRINT):
        if path.exists():
            path.unlink()


@pytest.fixture(autouse=True)
def _isolated_data() -> None:
    _restore_data_fixtures()
    _purge_outputs()


def _build() -> None:
    proc = subprocess.run(
        ["bash", str(ENV / "scripts" / "build_all.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"build failed:\n{proc.stdout}\n{proc.stderr}"


def _recover_all(*, keep: bool = False) -> subprocess.CompletedProcess[str]:
    if not keep:
        _purge_outputs()
    return subprocess.run(
        [CTL, "recover-all"],
        capture_output=True,
        text=True,
        check=False,
    )


def _recover_one(label: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [CTL, "recover-one", label],
        capture_output=True,
        text=True,
        check=False,
    )


def _require_driver_ok(
    proc: subprocess.CompletedProcess[str] | None = None, *, keep: bool = False
) -> subprocess.CompletedProcess[str]:
    proc = _recover_all(keep=keep) if proc is None else proc
    if proc.returncode != 0:
        raise AssertionError(f"driver failed: {proc.stderr or proc.stdout}")
    return proc


def _list_limits(*, boot: int = 1) -> dict[str, dict]:
    env = os.environ.copy()
    if boot >= 2:
        env["S8_BOOT_EPOCH"] = str(boot)
    else:
        env.pop("S8_BOOT_EPOCH", None)
    proc = subprocess.run(
        [CLIENT, "list"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    out: dict[str, dict] = {}
    for line in proc.stdout.splitlines():
        if not line.startswith("label="):
            continue
        parts = {}
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                parts[k] = v
        label = parts.get("label", "")
        if label:
            out[label] = parts
    return out


def _ledger_rows() -> dict[str, dict]:
    doc = json.loads(LEDGER.read_text())
    return {row["run_label"]: row for row in doc["rows"]}


def _ledger_row(label: str) -> dict:
    row = _ledger_rows().get(label)
    if row is None:
        raise KeyError(label)
    return row


def _active_labels() -> list[str]:
    return [label for label, row in _ledger_rows().items() if not row.get("retired")]


def _retired_labels() -> list[str]:
    return [label for label, row in _ledger_rows().items() if row.get("retired")]


def _matrix_attach(label: str) -> str:
    path = MATRIX_M02 if label in {"c03", "c04"} else MATRIX_M01
    return json.loads(path.read_text())["keys"][label]


def _load_stream_segments(label: str) -> list[StreamSeg]:
    path = ENV / "data" / "k7" / label / "stream.jsonl"
    out: list[StreamSeg] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            out.append(StreamSeg("", 0, "", "", ok=False))
            continue
        out.append(
            StreamSeg(
                segment_id=str(row.get("segment_id", "")),
                era=int(row.get("era", 0)),
                attach_id=str(row.get("attach_id", "")),
                kind=str(row.get("kind", "")),
                ok=True,
            )
        )
    return out


def _expected_apply_ids(label: str) -> frozenset[str]:
    """Apply transcript per recovery_semantics.md tombstone purge and kind rules."""
    retained: list[StreamSeg] = []
    for seg in _load_stream_segments(label):
        if not seg.ok:
            continue
        if seg.kind == "tombstone":
            retained = [s for s in retained if s.era > seg.era]
            continue
        if seg.kind in {"residue", "repairable"}:
            continue
        if seg.kind in {"sealed", "commit"} and seg.segment_id:
            retained.append(seg)
    return frozenset(s.segment_id for s in retained)


def _expected_head_era(label: str) -> int:
    """Highest commit era from stream rows after recovery_semantics.md."""
    best = 0
    for seg in _load_stream_segments(label):
        if seg.ok and seg.kind == "commit" and seg.era > best:
            best = seg.era
    return best


def _load_run() -> dict:
    return json.loads(RUN.read_text())


def _head_entry(label: str, entries: list[dict]) -> dict:
    for ev in entries:
        if ev["run_label"] == label and ev["phase"] == "head":
            return ev
    raise KeyError(f"missing head entry for {label}")


def _binding_probe_fixtures() -> dict[str, str | int]:
    raw = (ENV / "config" / "bindings.toml").read_text()
    out: dict[str, str | int] = {}
    section = ""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "probe_fixtures" or "=" not in line:
            continue
        key, val = [p.strip() for p in line.split("=", 1)]
        val = val.strip('"')
        out[key] = int(val) if val.isdigit() else val
    return out


def _stamp_era(label: str) -> int:
    return int((M9 / f"{label}.stamp").read_text().strip())


def test_replay_segment_retention_under_corruption() -> None:
    """Doc replay rules: skip corrupt lines; tombstone purges prior apply rows."""
    _require_driver_ok()
    entries = _load_run()["entries"]
    for label in FIXTURES:
        applied = {
            e["segment_id"]
            for e in entries
            if e["run_label"] == label and e["phase"] == "apply"
        }
        assert applied == set(_expected_apply_ids(label))
    tombstone_ids = {
        seg.segment_id
        for label in FIXTURES
        for seg in _load_stream_segments(label)
        if seg.ok and seg.kind == "tombstone" and seg.segment_id
    }
    tombstone_apply = {
        e["segment_id"]
        for e in entries
        if e["phase"] == "apply" and e["segment_id"] in tombstone_ids
    }
    assert tombstone_apply == set()
    skipped_kinds = {"residue", "repairable"}
    skipped_ids = {
        seg.segment_id
        for label in FIXTURES
        for seg in _load_stream_segments(label)
        if seg.ok and seg.kind in skipped_kinds and seg.segment_id
    }
    skipped_apply = {
        e["segment_id"]
        for e in entries
        if e["phase"] == "apply" and e["segment_id"] in skipped_ids
    }
    assert skipped_apply == set()


def test_cross_subsystem_tuple_convergence() -> None:
    """Active labels: matrix attach, stream-derived era, ledger, stamps, and head rows agree."""
    _require_driver_ok()
    listed = _list_limits(boot=1)
    entries = _load_run()["entries"]
    for label in _active_labels():
        want_era = _expected_head_era(label)
        want_attach = _matrix_attach(label)
        row = _ledger_row(label)
        assert int(listed[label]["hard_limit"]) == row["hard_limit"]
        assert int(listed[label]["era"]) == want_era == row["era"]
        assert listed[label]["attach_id"] == want_attach == row["attach_id"]
        assert _stamp_era(label) == want_era
        head = _head_entry(label, entries)
        assert head["era"] == want_era
        assert head["attach_id"] == want_attach
        stream_attach = {
            seg.attach_id
            for seg in _load_stream_segments(label)
            if seg.ok and seg.kind == "commit"
        }
        if stream_attach and want_attach not in stream_attach:
            assert want_attach == _matrix_attach(label)


def test_fleet_idempotent_after_staging_reinject() -> None:
    """Second recover-all after orphan/j4 reinjection reproduces prior graded artifacts."""
    _require_driver_ok()
    first_run = RUN.read_bytes()
    first_fp = FINGERPRINT.read_bytes()
    (M9 / "orphan.tmp").write_text("noise\n")
    (J4 / "seg_003.jsonl").write_text(
        '{"run_label":"c03","era":1,"kind":"commit","hard_limit":1}\n'
    )
    _require_driver_ok(_recover_all(keep=True))
    assert RUN.read_bytes() == first_run
    assert FINGERPRINT.read_bytes() == first_fp
    tmp_names = {p.name for p in M9.glob("*.tmp")}
    assert tmp_names.isdisjoint({"orphan.tmp"})
    assert list(J4.iterdir()) == []


def test_fingerprint_matches_run_form_canonicalization() -> None:
    """state_fingerprint.txt follows run_form.md slim-object sorting and t_ms zeroing."""
    _require_driver_ok()
    doc = _load_run()
    assert FINGERPRINT.read_text().strip() == _entry_hash(doc["entries"])
    for ev in doc["entries"]:
        assert ev["t_ms"] == 0


def test_multi_epoch_limit_and_attach_stability() -> None:
    """Epochs 2–3 preserve hard_limit, era, and attach_id for every active label."""
    _require_driver_ok()
    baseline = _list_limits(boot=1)
    for epoch in (2, 3):
        later = _list_limits(boot=epoch)
        for label in _active_labels():
            for field in ("hard_limit", "era", "attach_id"):
                assert later[label][field] == baseline[label][field]
        for label in _retired_labels():
            if label in later:
                assert int(later[label].get("hard_limit", 0)) == 0


def test_staging_fold_and_head_stamp_chain() -> None:
    """Only active .tmp remains; orphan.tmp gone; stamp era matches head and ledger."""
    _require_driver_ok()
    tmp_names = {p.name for p in M9.glob("*.tmp")}
    assert tmp_names.isdisjoint({"orphan.tmp"})
    entries = _load_run()["entries"]
    for label in _active_labels():
        assert (M9 / f"{label}.tmp").is_file()
        era = _expected_head_era(label)
        head = _head_entry(label, entries)
        assert _stamp_era(label) == era == head["era"] == _ledger_row(label)["era"]


def test_recover_one_label_quarantine() -> None:
    """recover-one touches one label only; graded outputs absent until recover-all."""
    _require_driver_ok()
    fixtures = _binding_probe_fixtures()
    stale_era = int(fixtures["c01_stale_era"])
    stale_attach = str(fixtures["c01_stale_attach"])
    doc = json.loads(LEDGER.read_text())
    for row in doc["rows"]:
        if row["run_label"] == "c01":
            row["era"] = stale_era
            row["attach_id"] = stale_attach
    LEDGER.write_text(json.dumps(doc, indent=2) + "\n")
    c01_stamp_before = (M9 / "c01.stamp").read_text()
    c02_row_before = dict(_ledger_row("c02"))
    _purge_outputs()
    proc = _recover_one("c02")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert len([p for p in (RUN, FINGERPRINT) if p.is_file()]) == 0
    c01_after = _ledger_row("c01")
    assert c01_after["era"] == stale_era
    assert c01_after["attach_id"] == stale_attach
    assert (M9 / "c01.stamp").read_text() == c01_stamp_before
    c02_after = _ledger_row("c02")
    assert c02_after["era"] == c02_row_before["era"]
    assert c02_after["attach_id"] == c02_row_before["attach_id"]
    assert c02_after["hard_limit"] == c02_row_before["hard_limit"]
    _require_driver_ok()
    listed = _list_limits(boot=1)
    for label in _active_labels():
        assert int(listed[label]["hard_limit"]) == _ledger_row(label)["hard_limit"]


def test_journal_tail_collapsed_before_epoch_probe() -> None:
    """Fixture j4 tails exist pre-recovery, collapse to empty, epoch-2 actives stay stable."""
    assert any(p.is_file() for p in J4.iterdir())
    _require_driver_ok()
    assert list(J4.iterdir()) == []
    baseline = _list_limits(boot=1)
    later = _list_limits(boot=2)
    for label in _active_labels():
        assert int(later[label]["hard_limit"]) == int(baseline[label]["hard_limit"])
        assert int(later[label]["era"]) == int(baseline[label]["era"])
        assert later[label]["attach_id"] == baseline[label]["attach_id"]


def test_delayed_seal_reconciles_stale_ledger_eras() -> None:
    """Stale pre-recovery ledger eras reconcile to stream commit maxima after recover-all."""
    _require_driver_ok()
    for label in ("c01", "c02"):
        assert _ledger_row(label)["era"] == _expected_head_era(label)
    listed = _list_limits(boot=1)
    for label in ("c01", "c02"):
        assert int(listed[label]["era"]) == _expected_head_era(label)


def test_driver_regenerates_and_rejects_static_cheat() -> None:
    """Pre-written output files are replaced; fingerprint tracks recomputed entries."""
    _build()
    _purge_outputs()
    RUN.parent.mkdir(parents=True, exist_ok=True)
    RUN.write_text('{"schema":"recovery_run.v1","entries":[]}\n')
    FINGERPRINT.write_text("deadbeef\n")
    _require_driver_ok()
    doc = _load_run()
    assert doc["schema"] == "recovery_run.v1"
    assert len(doc["entries"]) > 0
    assert FINGERPRINT.read_text().strip() == _entry_hash(doc["entries"])
    for label in _active_labels():
        assert _head_entry(label, doc["entries"])["attach_id"] == _matrix_attach(label)


def test_tombstone_purge_does_not_cross_labels() -> None:
    """Tombstone on c03 must not alter c01 apply transcript composition."""
    _require_driver_ok()
    entries = _load_run()["entries"]
    c01_apply = {
        e["segment_id"]
        for e in entries
        if e["run_label"] == "c01" and e["phase"] == "apply"
    }
    assert c01_apply == set(_expected_apply_ids("c01"))
    c03_apply = {
        e["segment_id"]
        for e in entries
        if e["run_label"] == "c03" and e["phase"] == "apply"
    }
    assert c03_apply == set(_expected_apply_ids("c03"))
    assert "t0" not in c03_apply


def test_sealed_rows_included_in_apply_transcript() -> None:
    """Sealed segments appear as apply rows when not purged by tombstone rules."""
    _require_driver_ok()
    entries = _load_run()["entries"]
    sealed_ids = {
        seg.segment_id
        for label in FIXTURES
        for seg in _load_stream_segments(label)
        if seg.ok and seg.kind == "sealed" and seg.segment_id
    }
    retained_sealed = sealed_ids & {
        seg_id for seg_id in _expected_apply_ids("c01") | _expected_apply_ids("c02")
        | _expected_apply_ids("c03") | _expected_apply_ids("c04")
    }
    apply_ids = {e["segment_id"] for e in entries if e["phase"] == "apply"}
    assert retained_sealed.issubset(apply_ids)
