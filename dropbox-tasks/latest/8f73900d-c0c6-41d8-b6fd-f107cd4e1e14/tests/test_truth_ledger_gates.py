"""Truth ledger capture sequence gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_outputs import (
    PATH_INSPECT_MANIFEST,
    PATH_PLAN_SEAL,
    PATH_ROLLBACK_PLAN,
    PATH_TRUTH_LEDGER,
    PATH_WAVE_SNAPSHOT,
    _rebuild_ctl,
    _run,
    reference_plan_hash,
    reference_rollback_steps,
    validate_ok,
)


class TestTruthLedgerCapture:
    @pytest.fixture(autouse=True)
    def rebuild(self):
        _rebuild_ctl()

    def test_inspect_writes_truth_ledger(self):
        """rollback-policy.md requires truth-ledger.json with capture_sequence and incident_id."""
        ledger_path = Path(PATH_TRUTH_LEDGER)
        if ledger_path.is_file():
            ledger_path.unlink()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr
        ledger = json.loads(ledger_path.read_text())
        assert ledger["capture_sequence"] >= 1
        assert ledger["incident_id"] == "inc-4429"

    def test_inspect_manifest_binds_capture_sequence(self):
        """inspect-manifest capture_sequence must match truth-ledger from same inspect run."""
        _run(["/app/bin/rollbackctl", "inspect"])
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        ledger = json.loads(Path(PATH_TRUTH_LEDGER).read_text())
        assert manifest.get("capture_sequence") == ledger["capture_sequence"]

    def test_plan_rejects_stale_truth_ledger_sequence(self):
        """plan must refuse when truth-ledger capture_sequence disagrees with manifest."""
        _run(["/app/bin/rollbackctl", "inspect"])
        ledger_path = Path(PATH_TRUTH_LEDGER)
        ledger = json.loads(ledger_path.read_text())
        saved_ledger = ledger_path.read_text()
        ledger["capture_sequence"] = ledger.get("capture_sequence", 1) + 99
        ledger_path.write_text(json.dumps(ledger, indent=2))
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0
        ledger_path.write_text(saved_ledger)

    def test_plan_requires_truth_ledger_file(self):
        """plan must refuse when truth-ledger.json is missing after inspect."""
        _run(["/app/bin/rollbackctl", "inspect"])
        ledger_path = Path(PATH_TRUTH_LEDGER)
        saved = ledger_path.read_text()
        ledger_path.unlink()
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0
        ledger_path.write_text(saved)

    def test_reinspect_bumps_capture_sequence(self):
        """Second inspect must increment capture_sequence and refresh manifest binding."""
        _run(["/app/bin/rollbackctl", "inspect"])
        first = json.loads(Path(PATH_TRUTH_LEDGER).read_text())["capture_sequence"]
        _run(["/app/bin/rollbackctl", "inspect"])
        second = json.loads(Path(PATH_TRUTH_LEDGER).read_text())["capture_sequence"]
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert second == first + 1
        assert manifest["capture_sequence"] == second

    def test_plan_hash_requires_sorted_step_lines(self):
        """wave-egress-schema.md sorts step lines before hashing plan content."""
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        expected = reference_plan_hash(plan["steps"], plan["release"])
        assert plan["hash"] == expected
        assert plan["steps"] == reference_rollback_steps()

    def test_plan_writes_wave_midpipe_snapshot(self):
        """plan emit must write wave-midpipe-snapshot binding capture_sequence and digests."""
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        snapshot_path = Path(PATH_WAVE_SNAPSHOT)
        assert snapshot_path.is_file()
        snapshot = json.loads(snapshot_path.read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert snapshot["capture_sequence"] == manifest["capture_sequence"]
        assert snapshot["plan_hash"] == plan["hash"]
        assert snapshot["manifest_release_digest"] == manifest["release_digest"]


class TestTb3TruthLedgerTraps:
    def test_hidden_truth_ledger_fixture_binding(self):
        """Hidden probe expects manifest and ledger capture_sequence alignment."""
        hidden = json.loads(
            (Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-truth-ledger.json").read_text()
        )
        probe = hidden["probe"]
        assert isinstance(probe, str) and probe
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        ledger = json.loads(Path(hidden["ledger_path"]).read_text())
        assert manifest[hidden["manifest_field"]] == ledger[hidden["manifest_field"]]
        assert ledger["incident_id"] == hidden["incident_id"]

    def test_apply_requires_truth_ledger_match(self):
        """apply-rollback must fail when truth-ledger capture_sequence is stale."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        ledger_path = Path(PATH_TRUTH_LEDGER)
        ledger = json.loads(ledger_path.read_text())
        saved = ledger_path.read_text()
        ledger["capture_sequence"] = ledger.get("capture_sequence", 1) + 50
        ledger_path.write_text(json.dumps(ledger, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
        ledger_path.write_text(saved)

    def test_ingest_only_manifest_patch_still_fails_plan(self):
        """Writing inspect-manifest without truth-ledger must not satisfy plan emit."""
        _rebuild_ctl()
        manifest_path = Path(PATH_INSPECT_MANIFEST)
        ledger_path = Path(PATH_TRUTH_LEDGER)
        if manifest_path.is_file():
            manifest_path.unlink()
        if ledger_path.is_file():
            ledger_path.unlink()
        _run(["/app/bin/rollbackctl", "inspect"])
        if ledger_path.is_file():
            ledger_path.unlink()
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0

    def test_apply_rejects_stale_wave_snapshot(self):
        """apply-rollback must fail when wave-midpipe-snapshot capture_sequence is stale."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        _run(["/app/bin/rollbackctl", "inspect"])
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0

    def test_hidden_wave_snapshot_fixture_binding(self):
        """Hidden probe expects snapshot capture_sequence aligned with manifest."""
        hidden = json.loads(
            (Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-wave-snapshot-trap.json").read_text()
        )
        assert isinstance(hidden.get("probe"), str) and hidden["probe"]
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        snapshot = json.loads(Path(PATH_WAVE_SNAPSHOT).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert snapshot[hidden["snapshot_field"]] == manifest[hidden["manifest_field"]]


class TestWaveSealSortedHash:
    def test_emit_plan_seal_matches_sorted_hash(self):
        """plan-seal plan_hash must bind sorted step-line content digest."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        seal = json.loads(Path(PATH_PLAN_SEAL).read_text())
        assert seal["plan_hash"] == reference_plan_hash(plan["steps"], plan["release"])
