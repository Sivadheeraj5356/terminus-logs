"""Verifier for cron-dst-double-fire (cxf prefix)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

APP = Path("/app")
ENV = APP / "environment"
TOOLS = APP / "tools"
DATA = APP / "data"
OUT = APP / "output"
LEDGER = OUT / "schedule_ledger.json"
STEP = OUT / "step"

PANES = ("backward", "forward", "resume")
ENV_MAP = {
    "backward": DATA / "windows" / "backward" / "window.conf",
    "forward": DATA / "windows" / "forward" / "window.conf",
    "resume": DATA / "windows" / "resume" / "window.conf",
}
TRACE_MAP = {
    "backward": DATA / "traces" / "backward.rows",
    "forward": DATA / "traces" / "forward.rows",
    "resume": DATA / "traces" / "resume.rows",
}


def _rebuild_tools() -> None:
    # Drop stale installed binaries first so a failed rebuild cannot silently
    # keep passing against earlier successful /app/tools copies.
    for name in ("step_tool", "pack_tool"):
        stale = TOOLS / name
        if stale.exists():
            stale.unlink()
    build = subprocess.run(
        ["make", "-C", "/app/environment", "clean", "all"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr or build.stdout
    for name in ("step_tool", "pack_tool"):
        src = ENV / "build" / name
        assert src.is_file(), f"missing build product {src}"
        copy = subprocess.run(
            ["cp", str(src), str(TOOLS / name)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert copy.returncode == 0, copy.stderr or copy.stdout
        assert (TOOLS / name).is_file()


def _clear_step_tree(step_root: Path = STEP) -> None:
    commit_path = step_root / "commit_log.tab"
    if commit_path.exists():
        commit_path.unlink()
    era_path = step_root / "boot_era.rec"
    if era_path.exists():
        era_path.unlink()
    if step_root.exists():
        for child in step_root.iterdir():
            if child.is_dir():
                for f in child.rglob("*"):
                    if f.is_file():
                        f.unlink()


def _step_pane(pane: str, out_dir: Path | None = None) -> None:
    target = out_dir or (STEP / pane)
    proc = subprocess.run(
        [
            "/app/tools/step_tool",
            "--pane",
            pane,
            "--env",
            str(ENV_MAP[pane]),
            "--trace",
            str(TRACE_MAP[pane]),
            "--out",
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def _pack(out_path: Path = LEDGER, step_root: Path = STEP) -> None:
    proc = subprocess.run(
        ["/app/tools/pack_tool", "--step-root", str(step_root), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def _run_pipeline(step_root: Path = STEP) -> dict:
    _rebuild_tools()
    _clear_step_tree(step_root)
    for pane in PANES:
        _step_pane(pane, step_root / pane)
    _pack(LEDGER, step_root)
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _digest_from_rows(rows: list[dict]) -> str:
    lines = [
        f"{r['cycle']},{r['window']},{r['civil_key']},{r['wall_offset']},{r['seq']},{r['octets']}"
        for r in rows
    ]
    blob = "\n".join(sorted(lines)) + "\n"
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256"],
        input=blob,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip().split()[-1]


def _rows_for_pane(doc: dict, pane: str) -> list[dict]:
    return [r for r in doc["rows"] if r["window"] == pane]


def _day_keys(rows: list[dict]) -> set[str]:
    out: set[str] = set()
    for r in rows:
        key = r["civil_key"]
        out.add(key[:8] if len(key) >= 8 else key)
    return out


class TestCxfSuite:
    def test_cxf_m01_promote(self) -> None:
        """Forward seeds hour-finest keys in the commit log before resume catch-up."""
        doc = _run_pipeline()
        assert doc["ledger_digest"] == _digest_from_rows(doc["rows"])
        forward = _rows_for_pane(doc, "forward")
        assert "2024031202" in {r["civil_key"] for r in forward}
        assert "2024031002" in {r["civil_key"] for r in forward}
        resume = _rows_for_pane(doc, "resume")
        boot = [r for r in resume if r["civil_key"].startswith("20240312")]
        assert len(boot) == 1
        assert boot[0]["seq"] < 100
        commit_text = (STEP / "commit_log.tab").read_text(encoding="utf-8")
        assert "2024031202" in commit_text
        assert "2024031002" in commit_text

    def test_cxf_m02_gap(self) -> None:
        """Spring gap-hour rows appear for each absent-hour seed with hour suffix 02."""
        _run_pipeline()
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        forward = _rows_for_pane(doc, "forward")
        hour_rows = [r for r in forward if len(r["civil_key"]) > 8]
        assert len(hour_rows) == 2
        assert {r["civil_key"][8:10] for r in hour_rows} == {"02"}
        assert {"2024031002", "2024031202"} <= {r["civil_key"] for r in hour_rows}
        commit_text = (STEP / "commit_log.tab").read_text(encoding="utf-8")
        assert "2024031002" in commit_text
        assert "2024031202" in commit_text

    def test_cxf_m03_era(self) -> None:
        """Boot-era marker records a generation after resume with full commit coverage."""
        _run_pipeline()
        era_text = (STEP / "boot_era.rec").read_text(encoding="utf-8").strip()
        assert int(era_text) >= 1
        commit_text = (STEP / "commit_log.tab").read_text(encoding="utf-8")
        lines = [ln for ln in commit_text.splitlines() if ln.strip()]
        assert len(lines) >= 4
        panes = {ln.split("\t", 1)[0] for ln in lines}
        assert panes >= {"backward", "forward", "resume"}

    def test_cxf_m04_staged(self) -> None:
        """Incremental per-window stepping shares the commit log and matches one-shot digest."""
        _rebuild_tools()
        _clear_step_tree()
        for pane in PANES:
            _step_pane(pane)
        _pack()
        staged_digest = json.loads(LEDGER.read_text(encoding="utf-8"))["ledger_digest"]
        full_doc = _run_pipeline()
        assert full_doc["ledger_digest"] == staged_digest

    def test_cxf_m05_slot(self) -> None:
        """Autumn fall-back collapses to one day row and persists durable slot state."""
        _run_pipeline()
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        backward = _rows_for_pane(doc, "backward")
        assert len(backward) == 1
        assert len(_day_keys(backward)) == 1
        assert backward[0]["civil_key"][:8] == "20231105"
        slot_path = STEP / "backward" / "slot_state.rec"
        assert slot_path.exists()
        assert slot_path.read_text(encoding="utf-8").strip() != ""

    def test_cxf_m06_defer(self) -> None:
        """Warm era + commit log: re-stepping resume defers boot gaps (false-green trap)."""
        _run_pipeline()
        _step_pane("resume")
        _pack()
        resume = _rows_for_pane(json.loads(LEDGER.read_text(encoding="utf-8")), "resume")
        # Only the timezone-skip fragment remains as first-pass work; the boot gap
        # stays deferred because era already exists and the key is committed.
        assert len(resume) == 1
        assert resume[0]["civil_key"] == "20240311"
        assert resume[0]["seq"] < 100
        assert all(r["seq"] < 100 for r in resume)

    def test_cxf_m07_z3(self) -> None:
        """Resume window keeps exactly one first-pass row for the timezone-skip fragment."""
        doc = _run_pipeline()
        resume = _rows_for_pane(doc, "resume")
        keys = [r["civil_key"] for r in resume]
        assert sum(1 for k in keys if k == "20240311") == 1

    def test_cxf_m08_w4(self) -> None:
        """Resume window emits exactly two distinct rows with no recovery duplicates."""
        doc = _run_pipeline()
        resume = _rows_for_pane(doc, "resume")
        keys = [r["civil_key"] for r in resume]
        assert len(resume) == 2
        assert len(set(keys)) == 2
        assert "20240311" in keys
        assert any(k.startswith("20240312") for k in keys)

    def test_cxf_m09_v1(self) -> None:
        """Second backward step keeps a single collapsed day row (no double-fire growth)."""
        _run_pipeline()
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        first_rows = _rows_for_pane(doc, "backward")
        first_keys = _day_keys(first_rows)
        assert len(first_rows) == 1
        assert len(first_keys) == 1
        _step_pane("backward")
        _pack()
        doc2 = json.loads(LEDGER.read_text(encoding="utf-8"))
        second_rows = _rows_for_pane(doc2, "backward")
        second_keys = _day_keys(second_rows)
        assert len(second_rows) == 1
        assert second_keys == first_keys

    def test_cxf_m10_u0(self) -> None:
        """Resume recovery pass does not add duplicate civil keys already committed."""
        doc = _run_pipeline()
        resume = _rows_for_pane(doc, "resume")
        first_pass = [r for r in resume if r["seq"] < 100]
        recovery = [r for r in resume if r["seq"] >= 100]
        assert len(first_pass) == 2
        assert len(recovery) == 0
        assert len(doc["rows"]) >= 3

    def test_cxf_m11_stale(self) -> None:
        """Hand-edited window rows.tab without re-step must not preserve the correct digest."""
        doc = _run_pipeline()
        good_digest = doc["ledger_digest"]
        forward_rows = STEP / "forward" / "rows.tab"
        forward_rows.write_text("9\tforward\t99999999\t0\t1\t64\n", encoding="utf-8")
        _pack()
        stale = json.loads(LEDGER.read_text(encoding="utf-8"))["ledger_digest"]
        assert stale != good_digest
        replay = _run_pipeline()
        assert replay["ledger_digest"] == good_digest

    def test_cxf_m12_restale(self) -> None:
        """Re-stepping resume without a boot-era marker must not emit recovery rows."""
        _run_pipeline()
        era_path = STEP / "boot_era.rec"
        assert era_path.exists()
        era_path.unlink()
        _step_pane("resume")
        _pack()
        resume = _rows_for_pane(json.loads(LEDGER.read_text(encoding="utf-8")), "resume")
        recovery = [r for r in resume if r["seq"] >= 100]
        assert len(recovery) == 0
        assert len(resume) == 2

    def test_cxf_m13_chain(self) -> None:
        """Resume boot-gap first pass emits while era is zero; recovery waits for era and commit log."""
        _rebuild_tools()
        _clear_step_tree()
        _step_pane("backward")
        _step_pane("forward")
        _step_pane("resume")
        _pack()
        partial = json.loads(LEDGER.read_text(encoding="utf-8"))
        resume = _rows_for_pane(partial, "resume")
        assert len(resume) == 2
        assert len([r for r in resume if r["seq"] >= 100]) == 0
        assert int((STEP / "boot_era.rec").read_text(encoding="utf-8").strip()) >= 1
        full = _run_pipeline()
        assert full["ledger_digest"] == partial["ledger_digest"]

    def test_cxf_m14_recovery(self) -> None:
        """Later resume step with era present emits one genuine recovery row for an uncommitted boot gap."""
        _run_pipeline()
        assert int((STEP / "boot_era.rec").read_text(encoding="utf-8").strip()) >= 1
        commit_path = STEP / "commit_log.tab"
        assert commit_path.exists()
        commit_path.unlink()
        _step_pane("resume")
        _pack()
        resume = _rows_for_pane(json.loads(LEDGER.read_text(encoding="utf-8")), "resume")
        first_pass = [r for r in resume if r["seq"] < 100]
        recovery = [r for r in resume if r["seq"] >= 100]
        # Era present: first pass must defer the boot gap (only tz-skip remains).
        assert len(first_pass) == 1
        assert first_pass[0]["civil_key"] == "20240311"
        assert len(recovery) == 1
        # Commit log was cleared, so promotion from forward is unavailable; the
        # recovery row keeps the boot-gap fragment day key.
        assert recovery[0]["civil_key"] == "20240312"
        assert recovery[0]["seq"] >= 100
        assert sum(1 for r in recovery if r["civil_key"] == "20240311") == 0
