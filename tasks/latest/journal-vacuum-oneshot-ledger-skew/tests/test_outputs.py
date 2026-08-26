from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from reference_sim import load_pack, sha32, simulate, stems

ROOT = Path("/app")
ENV = ROOT / "environment"
FIXTURES_DIR = ENV / "pack"
VERIFY_BIN = Path("/tmp/verify-journal-runs")

REPORT_PATH = ROOT / "output" / "run_records.json"
TRACE_PATH = ROOT / "output" / "export_trace.jsonl"
JOURNAL_PATH = ROOT / "output" / "span_journal.jsonl"
MANIFEST_PATH = ROOT / "output" / "completion_manifest.jsonl"
AUDIT_PATH = ROOT / "output" / "run_audit.jsonl"
LEDGER_STATE_PATH = ROOT / "output" / "run_ledger.state"
RESUME_PATH = ROOT / "state" / "resume.offset"
SEGMENT_CACHE_PATH = ROOT / "state" / "segment.cache.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            out.append(json.loads(raw))
    return out


def _rows_by_label(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["fixture_label"]: r for r in rows}


def _build_binary() -> None:
    subprocess.run(
        ["go", "build", "-o", str(VERIFY_BIN), "/app/environment/cmd/verify_journal_runs"],
        cwd=str(ENV),
        check=True,
        capture_output=True,
        text=True,
    )


def _run_verify(fixtures_dir: Path = FIXTURES_DIR, *, reset_state: bool = True) -> None:
    _build_binary()
    outputs = [REPORT_PATH, TRACE_PATH, JOURNAL_PATH, MANIFEST_PATH, AUDIT_PATH]
    if reset_state:
        outputs.append(LEDGER_STATE_PATH)
    for p in outputs:
        if p.exists():
            p.unlink()
    if reset_state and SEGMENT_CACHE_PATH.exists():
        SEGMENT_CACHE_PATH.unlink()
    subprocess.run(
        [
            str(VERIFY_BIN),
            "--fixtures-dir",
            str(fixtures_dir),
            "--out",
            str(REPORT_PATH),
            "--trace-out",
            str(TRACE_PATH),
            "--journal-out",
            str(JOURNAL_PATH),
            "--manifest-out",
            str(MANIFEST_PATH),
            "--audit-out",
            str(AUDIT_PATH),
            "--ledger-state",
            str(LEDGER_STATE_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_delayed_sidecar_reconcile() -> None:
    """Cross-artifact seals must match simulation for all fixtures."""
    _run_verify()
    sim = simulate(FIXTURES_DIR)
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))["runs"]
    manifest = _read_jsonl(MANIFEST_PATH)
    audit = _read_jsonl(AUDIT_PATH)
    assert _rows_by_label(report) == _rows_by_label(sim["report"])
    assert _rows_by_label(manifest) == _rows_by_label(sim["manifest"])
    assert _rows_by_label(audit) == _rows_by_label(sim["audit"])


def test_recycle_wave_byte_totals() -> None:
    """Observed totals and terminal wave_end rows match simulated execution."""
    _run_verify()
    sim = simulate(FIXTURES_DIR)
    report = _rows_by_label(json.loads(REPORT_PATH.read_text(encoding="utf-8"))["runs"])
    trace = _read_jsonl(TRACE_PATH)
    sim_trace = sim["trace"]
    for stem in stems(FIXTURES_DIR):
        assert report[stem]["byte_span"]["observed_bytes"] == _rows_by_label(sim["report"])[stem]["byte_span"]["observed_bytes"]
        got_end = [r for r in trace if r["fixture_label"] == stem and r["phase"] == "wave_end"][-1]
        sim_end = [r for r in sim_trace if r["fixture_label"] == stem and r["phase"] == "wave_end"][-1]
        assert got_end["observed"] == sim_end["observed"]
        assert got_end["pending"] == 0


def test_large_wave_chunk_monotonicity() -> None:
    """Wave-chunk sequence for pack_m5 must match simulated ordering and counts."""
    _run_verify()
    sim = simulate(FIXTURES_DIR)
    got = [r for r in _read_jsonl(TRACE_PATH) if r["fixture_label"] == "pack_m5" and r["phase"] == "wave_chunk"]
    want = [r for r in sim["trace"] if r["fixture_label"] == "pack_m5" and r["phase"] == "wave_chunk"]
    assert [(r["observed"], r["pending"]) for r in got] == [(r["observed"], r["pending"]) for r in want]


def test_multi_recycle_checkpoint_totals() -> None:
    """Recycle checkpoints preserve observed totals and clear pending bytes."""
    _run_verify()
    rows = [r for r in _read_jsonl(TRACE_PATH) if r["fixture_label"] == "pack_m5"]
    before = [r for r in rows if r["phase"] == "recycle_before"]
    after = [r for r in rows if r["phase"] == "recycle_after"]
    assert len(before) == len(after) == 2
    for b, a in zip(before, after, strict=True):
        assert b["pending"] == 0 and a["pending"] == 0
        assert a["observed"] == b["observed"]


def test_span_journal_sequence_monotonic() -> None:
    """Journal sequence must be contiguous from 1..N with no gaps."""
    _run_verify()
    seqs = [r["seq"] for r in _read_jsonl(JOURNAL_PATH)]
    assert seqs == list(range(1, len(seqs) + 1))


def test_span_journal_link_integrity() -> None:
    """Journal links must chain deterministically using pending-aware payload."""
    _run_verify()
    journal = _read_jsonl(JOURNAL_PATH)
    prev = "genesis"
    for row in journal:
        want = sha32(
            f"{prev}|{row['seq']}|{row['fixture_label']}|{row['phase']}|{row['observed']}|{row['pending']}"
        )
        assert row["link"] == want
        prev = row["link"]


def test_repeat_run_identical_seals() -> None:
    """Two fresh-state reruns must produce byte-identical links and audit seals."""
    links: list[list[str]] = []
    audits: list[list[str]] = []
    for _ in range(2):
        _run_verify(reset_state=True)
        links.append([r["link"] for r in _read_jsonl(JOURNAL_PATH)])
        audits.append([r["audit_seal"] for r in _read_jsonl(AUDIT_PATH)])
    assert links[0] == links[1]
    assert audits[0] == audits[1]


def test_regenerated_outputs_replace_tamper() -> None:
    """Tampered outputs are overwritten by a full verify regeneration."""
    REPORT_PATH.write_text('{"runs":[]}\n', encoding="utf-8")
    TRACE_PATH.write_text('{"fixture_label":"tampered"}\n', encoding="utf-8")
    JOURNAL_PATH.write_text('{"seq":0,"link":"tampered"}\n', encoding="utf-8")
    MANIFEST_PATH.write_text('{"fixture_label":"tampered"}\n', encoding="utf-8")
    AUDIT_PATH.write_text('{"fixture_label":"tampered"}\n', encoding="utf-8")
    LEDGER_STATE_PATH.write_text('{"run_count":0,"prev_audit_tail":"x","chain_seal":"x"}\n', encoding="utf-8")
    _run_verify()
    assert "tampered" not in JOURNAL_PATH.read_text(encoding="utf-8")
    runs = json.loads(REPORT_PATH.read_text(encoding="utf-8"))["runs"]
    assert len(runs) == len(stems(FIXTURES_DIR))
    assert set(_rows_by_label(runs).keys()) == set(stems(FIXTURES_DIR))


def test_cross_run_ledger_advance() -> None:
    """Ledger chain must include prior tail, current tail, run count, fixture count."""
    _run_verify(reset_state=True)
    first_ledger = json.loads(LEDGER_STATE_PATH.read_text(encoding="utf-8"))
    first_tail = _read_jsonl(AUDIT_PATH)[-1]["audit_seal"]
    _run_verify(reset_state=False)
    second_ledger = json.loads(LEDGER_STATE_PATH.read_text(encoding="utf-8"))
    second_tail = _read_jsonl(AUDIT_PATH)[-1]["audit_seal"]
    fixture_count = len(stems(FIXTURES_DIR))
    assert second_ledger["run_count"] == first_ledger["run_count"] + 1
    assert second_ledger["prev_audit_tail"] == second_tail
    assert second_ledger["chain_seal"] == sha32(
        f"{first_tail}|{second_tail}|{second_ledger['run_count']}|{fixture_count}"
    )


def test_stale_offset_preload_ignored() -> None:
    """Resume preload applies only when fixture and reader epoch both match."""
    _run_verify()
    got = _rows_by_label(json.loads(REPORT_PATH.read_text(encoding="utf-8"))["runs"])["pack_m3"]["byte_span"]["observed_bytes"]
    want = _rows_by_label(simulate(FIXTURES_DIR)["report"])["pack_m3"]["byte_span"]["observed_bytes"]
    assert got == want


def test_stale_segment_cache_epoch_ignored() -> None:
    """Segment cache preload applies only when fixture label and reader epoch both match."""
    SEGMENT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEGMENT_CACHE_PATH.write_text(
        json.dumps(
            {
                "entries": {
                    "pack_m6|deadbeef": {"observed_bytes": 99999, "reader_epoch": "deadbeef"},
                    "pack_m6|f6aa01": {"observed_bytes": 99999, "reader_epoch": "stale01"},
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _run_verify(reset_state=False)
    got = _rows_by_label(json.loads(REPORT_PATH.read_text(encoding="utf-8"))["runs"])["pack_m6"]["byte_span"]["observed_bytes"]
    want = _rows_by_label(simulate(FIXTURES_DIR)["report"])["pack_m6"]["byte_span"]["observed_bytes"]
    assert got == want


def test_overlay_chunk_divisor_fineness() -> None:
    """Manifest wave_chunks for pack_m5 must match config-driven chunk planning."""
    _run_verify()
    manifest = _rows_by_label(_read_jsonl(MANIFEST_PATH))
    want = _rows_by_label(simulate(FIXTURES_DIR)["manifest"])["pack_m5"]["wave_chunks"]
    assert manifest["pack_m5"]["wave_chunks"] == want


def test_runtime_pack_m_discovery(tmp_path: Path) -> None:
    """Runtime pack_m7 is discovered while non-pack files are ignored."""
    for stem in stems(FIXTURES_DIR):
        (tmp_path / f"{stem}.json").write_text(
            (FIXTURES_DIR / f"{stem}.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    base = load_pack("pack_m2", FIXTURES_DIR)
    (tmp_path / "pack_m7.json").write_text(json.dumps(base) + "\n", encoding="utf-8")
    (tmp_path / "scratch_fixture.json").write_text(json.dumps(base) + "\n", encoding="utf-8")
    _run_verify(tmp_path)
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))["runs"]
    labels = [r["fixture_label"] for r in report]
    assert "pack_m7" in labels
    assert "scratch_fixture" not in labels
    assert labels == sorted(labels)
