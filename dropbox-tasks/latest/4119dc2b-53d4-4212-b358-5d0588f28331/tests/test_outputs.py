"""Verifier for WASM capability sandbox recovery — cross-module replay workflows."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from driver.journal_runner import run_journal
from driver.recovery_runner import run_recovery

FIXTURES = Path("/tests/fixtures/wasm")
WITNESS = Path("/app/environment/fixtures/waves/recovery-witness.json")
OUT = Path("/app/output/sandbox_observations.json")
DATA = Path("/app/data/wasm")
ALLOWED_SOURCES = {"budget", "access", "boundary", "audit", "journal"}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _witness() -> dict:
    return json.loads(WITNESS.read_text())


def _run_audit() -> None:
    proc = subprocess.run(
        ["/app/environment/ops/probe/run-audit.sh"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.parametrize(
    "scenario_id",
    ["wave_alpha", "wave_beta", "wave_gamma", "wave_delta", "wave_epsilon", "wave_zeta"],
)
def test_wave_journal_matrix(scenario_id: str):
    """Wave scenarios must match frozen digests through the journal runner."""
    spec = _load(scenario_id)
    got = run_journal(spec)
    assert got["digest"] == spec["expected_digest"]


def test_order_trap():
    """Module ordering must change digest while primary replay stays canonical."""
    spec = _load("order_trap")
    primary = {k: v for k, v in spec.items() if k not in ("alt_ops", "alt_expected_digest", "expected_digest")}
    alt = {
        "modules": spec["alt_ops"],
        "host_calls": spec.get("host_calls", []),
        "fuel_budget": spec["fuel_budget"],
        "capabilities": spec.get("capabilities", []),
    }
    a = run_journal(primary)
    b = run_journal(alt)
    assert a["digest"] != b["digest"]
    assert a["digest"] == spec["expected_digest"]
    assert b["digest"] == spec["alt_expected_digest"]


def test_recovery_coupling_trap():
    """Live and replay legs must converge to witness digests with probe map."""
    spec = _load("replay_coupling_trap")
    doc = run_recovery(spec, DATA / "recovery-coupling")
    assert doc["live_digest"] == spec["expected_live_digest"]
    assert doc["replay_digest"] == spec["expected_replay_digest"]
    for key, value in spec["expected_probes"].items():
        assert doc["probes"][key] == value


def test_audit_pipeline_emits_observations():
    """Recovery audit must regenerate sandbox observations from the wave fixture."""
    witness = _witness()
    if OUT.is_file():
        OUT.unlink()
    _run_audit()
    assert OUT.is_file(), "sandbox_observations.json missing"
    payload = json.loads(OUT.read_text())
    assert "runs" in payload and "probes" in payload
    assert len(payload["runs"]) == 2
    replay = payload["runs"][1]
    assert replay["sandbox_digest"] == witness["replay_digest"]
    assert replay["metrics"][4] >= 0


def test_audit_idempotent():
    """Consecutive audit cycles must report identical replay digests."""
    witness = _witness()
    _run_audit()
    first = json.loads(OUT.read_text())
    _run_audit()
    second = json.loads(OUT.read_text())
    assert first["runs"][1]["sandbox_digest"] == second["runs"][1]["sandbox_digest"]
    assert first["runs"][1]["sandbox_digest"] == witness["replay_digest"]


def test_segment_provenance():
    """Observation segments must cite every sandbox subsystem source."""
    _run_audit()
    payload = json.loads(OUT.read_text())
    sources = set()
    for run in payload["runs"]:
        for seg in run.get("segments", []):
            sources.add(seg.get("source"))
    assert ALLOWED_SOURCES.issubset(sources)


def test_probe_witness_alignment():
    """Probe map must match the converged witness bundled with the recovery wave."""
    witness = _witness()
    _run_audit()
    payload = json.loads(OUT.read_text())
    probes = payload["probes"]
    for key, value in witness["probes"].items():
        assert probes[key] == value
    assert probes["live_digest"] == payload["runs"][0]["sandbox_digest"]
    assert probes["replay_digest"] == payload["runs"][1]["sandbox_digest"]
