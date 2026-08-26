"""Verifier for multi-level Haar soft-threshold instrument-trace denoising.

Independent numeric reference lives in haar_reference.py. Tests drive
/app/bin/haar-denoiser via subprocess and compare scientific products.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import haar_reference as ref
import pytest

BIN = Path("/app/bin/haar-denoiser")
DATA = Path("/app/data")
STATE = Path("/app/state")
OUTPUT = Path("/app/output")
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        [str(BIN), *args],
        text=True,
        capture_output=True,
        env=e,
        check=False,
    )


def clean_dirs() -> None:
    for d in (STATE, OUTPUT):
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*"):
            if p.is_file():
                p.unlink()


def full_pipeline(env: dict[str, str] | None = None) -> None:
    clean_dirs()
    for mode in ("ingest-traces", "decompose-threshold", "reconstruct-export"):
        cp = run_cli(mode, env=env)
        assert cp.returncode == 0, f"{mode} failed: {cp.stderr}"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_fixture(name: str, dest: Path) -> None:
    src = FIXTURES / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


@pytest.fixture()
def bundled_expected() -> dict:
    return ref.full_reference(DATA)


def test_version_prints_semver() -> None:
    """version mode prints the documented semver line."""
    cp = run_cli("version")
    assert cp.returncode == 0
    assert "haar-denoiser 0.1.0" in cp.stdout


def test_ingest_writes_snapshot_only(bundled_expected: dict) -> None:
    """ingest-traces seals trace-snapshot.json and must not write outputs."""
    clean_dirs()
    cp = run_cli("ingest-traces")
    assert cp.returncode == 0, cp.stderr
    snap = load(STATE / "trace-snapshot.json")
    assert snap["schema_version"] == 1
    assert snap["policy_revision_id"] == bundled_expected["policy_revision_id"]
    assert snap["mad_multiplier"] == pytest.approx(bundled_expected["mad_multiplier"])
    assert list(OUTPUT.glob("*.json")) == []


def test_threshold_policy_supersession_picks_newest() -> None:
    """Active policy must be greatest effective_at then revision_id (rev 3)."""
    clean_dirs()
    assert run_cli("ingest-traces").returncode == 0
    snap = load(STATE / "trace-snapshot.json")
    assert snap["policy_revision_id"] == 3
    assert snap["mad_multiplier"] == pytest.approx(1.0)
    assert snap["mad_multiplier"] != pytest.approx(0.25)


def test_decompose_writes_ledger_pack_and_journal(bundled_expected: dict) -> None:
    """decompose-threshold writes ledger, sealed pack, and journal without outputs."""
    clean_dirs()
    assert run_cli("ingest-traces").returncode == 0
    assert run_cli("decompose-threshold").returncode == 0
    ledger = load(STATE / "coeff-ledger.json")
    pack = load(STATE / "coeff-pack.json")
    journal = load(STATE / "threshold-journal.json")
    assert ledger["effective_levels"] == bundled_expected["effective_levels"]
    assert pack["schema_version"] == 2
    assert pack["policy_revision_id"] == bundled_expected["policy_revision_id"]
    assert journal["mad_sigma"] == pytest.approx(bundled_expected["mad_sigma"], rel=1e-9, abs=1e-12)
    assert journal["lambda0"] == pytest.approx(bundled_expected["lambda0"], rel=1e-9, abs=1e-12)
    assert list(OUTPUT.glob("*.json")) == []


def test_coeff_pack_seal_matches_reference() -> None:
    """pack_seal must bind snapshot digest, policy, pads, and coefficient order."""
    full_pipeline()
    snap = load(STATE / "trace-snapshot.json")
    pack = load(STATE / "coeff-pack.json")
    expected_seal = ref.pack_seal(
        pack["snapshot_digest"],
        int(pack["policy_revision_id"]),
        pack["entries"],
    )
    assert pack["pack_seal"] == expected_seal
    assert pack["policy_revision_id"] == snap["policy_revision_id"]
    assert pack["mad_multiplier"] == pytest.approx(snap["mad_multiplier"])


def test_mad_uses_finest_detail_only(bundled_expected: dict) -> None:
    """Journal MAD sigma must match finest-detail-only estimator."""
    full_pipeline()
    journal = load(STATE / "threshold-journal.json")
    assert journal["mad_sigma"] == pytest.approx(bundled_expected["mad_sigma"], rel=1e-9, abs=1e-12)


def test_approx_band_not_soft_thresholded(bundled_expected: dict) -> None:
    """Coarsest approximation coefficients must remain unthresholded."""
    full_pipeline()
    ledger = load(STATE / "coeff-ledger.json")
    for entry, exp in zip(ledger["entries"], bundled_expected["entries"]):
        assert len(entry["approx"]) == len(exp["approx"])
        for a, b in zip(entry["approx"], exp["approx"]):
            assert a == pytest.approx(b, rel=1e-9, abs=1e-12)


def test_detail_soft_threshold_matches_reference(bundled_expected: dict) -> None:
    """Detail bands after soft threshold match the independent reference."""
    full_pipeline()
    ledger = load(STATE / "coeff-ledger.json")
    for entry, exp in zip(ledger["entries"], bundled_expected["entries"]):
        assert len(entry["details"]) == len(exp["details"])
        for band, eband in zip(entry["details"], exp["details"]):
            assert len(band) == len(eband)
            for a, b in zip(band, eband):
                assert a == pytest.approx(b, rel=1e-9, abs=1e-12)


def test_denoised_traces_match_reference(bundled_expected: dict) -> None:
    """Reconstructed samples match orthonormal inverse after soft threshold."""
    full_pipeline()
    out = load(OUTPUT / "denoised-traces.json")
    assert out["policy_revision_id"] == bundled_expected["policy_revision_id"]
    assert out["effective_levels"] == bundled_expected["effective_levels"]
    assert len(out["traces"]) == len(bundled_expected["entries"])
    for tr, exp in zip(out["traces"], bundled_expected["entries"]):
        assert tr["trace_id"] == exp["trace_id"]
        assert len(tr["samples"]) == len(exp["denoised"])
        for a, b in zip(tr["samples"], exp["denoised"]):
            assert a == pytest.approx(b, rel=1e-9, abs=1e-12)


def test_noise_audit_energy_matches_reference(bundled_expected: dict) -> None:
    """Residual energy audit matches independent reconstruction energy."""
    full_pipeline()
    audit = load(OUTPUT / "noise-audit.json")
    assert audit["mad_sigma"] == pytest.approx(bundled_expected["mad_sigma"], rel=1e-9, abs=1e-12)
    assert audit["total_signal_energy"] == pytest.approx(
        bundled_expected["total_signal_energy"], rel=1e-9, abs=1e-12
    )
    assert audit["total_residual_energy"] == pytest.approx(
        bundled_expected["total_residual_energy"], rel=1e-9, abs=1e-12
    )
    assert audit["mean_relative_residual"] == pytest.approx(
        bundled_expected["mean_relative_residual"], rel=1e-9, abs=1e-12
    )
    assert audit["content_sha256"] == ref.file_sha256(OUTPUT / "denoised-traces.json")


def test_export_rejects_tampered_pack_seal() -> None:
    """reconstruct-export must reject a mutated pack_seal."""
    clean_dirs()
    assert run_cli("ingest-traces").returncode == 0
    assert run_cli("decompose-threshold").returncode == 0
    pack_path = STATE / "coeff-pack.json"
    pack = load(pack_path)
    pack["pack_seal"] = "0" * 64
    pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    for p in OUTPUT.glob("*.json"):
        p.unlink()
    cp = run_cli("reconstruct-export")
    assert cp.returncode != 0
    assert list(OUTPUT.glob("*.json")) == []


def test_export_rejects_stale_snapshot_after_decompose() -> None:
    """Changing snapshot policy after decompose must fail pack binding."""
    clean_dirs()
    assert run_cli("ingest-traces").returncode == 0
    assert run_cli("decompose-threshold").returncode == 0
    snap_path = STATE / "trace-snapshot.json"
    snap = load(snap_path)
    snap["policy_revision_id"] = int(snap["policy_revision_id"]) + 99
    snap["mad_multiplier"] = float(snap["mad_multiplier"]) + 0.5
    snap_path.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    for p in OUTPUT.glob("*.json"):
        p.unlink()
    cp = run_cli("reconstruct-export")
    assert cp.returncode != 0
    assert list(OUTPUT.glob("*.json")) == []


def test_relative_env_override_rejected() -> None:
    """Relative HAAR_DATA_DIR must be rejected."""
    cp = run_cli("ingest-traces", env={"HAAR_DATA_DIR": "relative/data"})
    assert cp.returncode != 0


def test_hidden_odd_length_repeat_pad(tmp_path: Path) -> None:
    """Hidden odd-length trace uses repeat-pad; reconstruction matches reference."""
    dest = tmp_path / "hidden-odd-pad"
    copy_fixture("hidden-odd-pad", dest)
    expected = ref.full_reference(dest)
    full_pipeline(env={"HAAR_DATA_DIR": str(dest)})
    out = load(OUTPUT / "denoised-traces.json")
    assert len(out["traces"]) == 1
    assert out["traces"][0]["trace_id"] == "T_ODD"
    for a, b in zip(out["traces"][0]["samples"], expected["entries"][0]["denoised"]):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-12)
    ledger = load(STATE / "coeff-ledger.json")
    assert ledger["entries"][0]["pad_lengths"][0] == 17


def test_hidden_level_clamp_no_invented_bands(tmp_path: Path) -> None:
    """Requested levels above L_max must clamp; no panic or extra bands."""
    dest = tmp_path / "hidden-level-clamp"
    copy_fixture("hidden-level-clamp", dest)
    expected = ref.full_reference(dest)
    assert expected["effective_levels"] == 3  # floor(log2(8))
    full_pipeline(env={"HAAR_DATA_DIR": str(dest)})
    ledger = load(STATE / "coeff-ledger.json")
    assert ledger["effective_levels"] == 3
    assert len(ledger["entries"][0]["details"]) == 3
    out = load(OUTPUT / "denoised-traces.json")
    for a, b in zip(out["traces"][0]["samples"], expected["entries"][0]["denoised"]):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-12)


def test_hidden_mixed_lengths_and_policy_tie(tmp_path: Path) -> None:
    """Equal effective_at ties break on revision; per-trace clamps stay independent."""
    dest = tmp_path / "hidden-mixed-tie"
    copy_fixture("hidden-mixed-tie", dest)
    expected = ref.full_reference(dest)
    assert expected["policy_revision_id"] == 7
    assert expected["mad_multiplier"] == pytest.approx(1.1)
    full_pipeline(env={"HAAR_DATA_DIR": str(dest)})
    snap = load(STATE / "trace-snapshot.json")
    assert snap["policy_revision_id"] == 7
    ledger = load(STATE / "coeff-ledger.json")
    by_id = {e["trace_id"]: e for e in ledger["entries"]}
    assert by_id["T_SHORT"]["effective_levels"] == 3
    assert by_id["T_ODD"]["effective_levels"] == 4
    assert by_id["T_ODD"]["pad_lengths"][0] == 17
    out = load(OUTPUT / "denoised-traces.json")
    for tr, exp in zip(out["traces"], expected["entries"]):
        for a, b in zip(tr["samples"], exp["denoised"]):
            assert a == pytest.approx(b, rel=1e-9, abs=1e-12)
    pack = load(STATE / "coeff-pack.json")
    assert pack["pack_seal"] == ref.pack_seal(
        pack["snapshot_digest"], int(pack["policy_revision_id"]), pack["entries"]
    )


def test_hidden_near_lambda_uses_soft_not_hard(tmp_path: Path) -> None:
    """Coefficients just above lambda must soft-shrink; hard-keep must not match."""
    dest = tmp_path / "hidden-near-lambda"
    copy_fixture("hidden-near-lambda", dest)
    expected = ref.full_reference(dest)
    hard = ref.hard_threshold_denoised(dest)
    soft = expected["entries"][0]["denoised"]
    assert sum(abs(a - b) for a, b in zip(soft, hard)) > 1e-6
    full_pipeline(env={"HAAR_DATA_DIR": str(dest)})
    out = load(OUTPUT / "denoised-traces.json")
    samples = out["traces"][0]["samples"]
    for a, b in zip(samples, soft):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-12)
    assert sum(abs(a - b) for a, b in zip(samples, hard)) > 1e-6


def test_idempotent_second_pipeline() -> None:
    """Second full pipeline on unchanged inputs is byte-identical."""
    full_pipeline()
    snap1 = (STATE / "trace-snapshot.json").read_bytes()
    ledger1 = (STATE / "coeff-ledger.json").read_bytes()
    pack1 = (STATE / "coeff-pack.json").read_bytes()
    journal1 = (STATE / "threshold-journal.json").read_bytes()
    den1 = (OUTPUT / "denoised-traces.json").read_bytes()
    audit1 = (OUTPUT / "noise-audit.json").read_bytes()
    assert run_cli("ingest-traces").returncode == 0
    assert run_cli("decompose-threshold").returncode == 0
    assert run_cli("reconstruct-export").returncode == 0
    assert (STATE / "trace-snapshot.json").read_bytes() == snap1
    assert (STATE / "coeff-ledger.json").read_bytes() == ledger1
    assert (STATE / "coeff-pack.json").read_bytes() == pack1
    assert (STATE / "threshold-journal.json").read_bytes() == journal1
    assert (OUTPUT / "denoised-traces.json").read_bytes() == den1
    assert (OUTPUT / "noise-audit.json").read_bytes() == audit1


def test_staging_policy_not_stale() -> None:
    """trace-snapshot must not carry the stale revision-1 multiplier."""
    clean_dirs()
    assert run_cli("ingest-traces").returncode == 0
    snap = load(STATE / "trace-snapshot.json")
    assert snap["policy_revision_id"] != 1
    assert snap["mad_multiplier"] != pytest.approx(0.25)


def test_export_requires_coeff_pack_file() -> None:
    """Missing coeff-pack.json must fail reconstruct-export."""
    clean_dirs()
    assert run_cli("ingest-traces").returncode == 0
    assert run_cli("decompose-threshold").returncode == 0
    (STATE / "coeff-pack.json").unlink()
    cp = run_cli("reconstruct-export")
    assert cp.returncode != 0
    assert list(OUTPUT.glob("*.json")) == []
