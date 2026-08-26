"""Verifier for Ambergate assay ledger — independent mixing/enrichment reference."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from assay_reference import build_products, evaluate_coin, load_json

APP = Path("/app")
BIN = APP / "bin" / "assay-ledger"
STATE = APP / "state"
OUTPUT = APP / "output"
DATA = APP / "data"
FIXTURES = Path("/opt/verifier-fixtures")

TOL = 5e-6


def run_ledger(*args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [str(BIN), *args],
        cwd=str(APP),
        capture_output=True,
        text=True,
        check=check,
        env=run_env,
    )


def reset_io() -> None:
    for d in (STATE, OUTPUT):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="module", autouse=True)
def _baseline_run():
    reset_io()
    run_ledger("analyze")
    yield


def _region_close(a: dict, b: dict) -> None:
    for k in (
        "f_au_min",
        "f_au_max",
        "f_ag_min",
        "f_ag_max",
        "f_cu_min",
        "f_cu_max",
    ):
        assert abs(float(a[k]) - float(b[k])) < TOL, (k, a[k], b[k])


def test_version_string():
    """version mode prints the assay-ledger binary identity."""
    cp = run_ledger("version")
    assert cp.stdout == "assay-ledger 1.0.0\n"


def test_snapshot_exists():
    """Analyze stage writes the authoritative assay snapshot."""
    assert (STATE / "assay-snapshot.json").is_file()


def test_outputs_exist():
    """Analyze publishes composition results, derivation trace, inconsistent list, and audit."""
    for name in (
        "composition-results.json",
        "derivation-trace.json",
        "inconsistent-coins.json",
        "audit.json",
    ):
        assert (OUTPUT / name).is_file()


def test_results_match_reference_statuses():
    """Per-coin status labels match the independent reference for the bundled catalog."""
    expected = build_products(APP)
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    assert got["schema_version"] == 1
    assert [c["coin_id"] for c in got["coins"]] == [c["coin_id"] for c in expected["coins"]]
    for e, g in zip(expected["coins"], got["coins"]):
        assert e["coin_id"] == g["coin_id"]
        assert e["status"] == g["status"]
        assert e.get("reason") == g.get("reason")


def test_feasible_regions_match_reference():
    """Feasible and density-only regions match independent bounds (never a collapsed point)."""
    expected = build_products(APP)
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    for e, g in zip(expected["coins"], got["coins"]):
        if e["status"] in ("feasible", "density_only"):
            assert g["feasible_region"] is not None
            _region_close(e["feasible_region"], g["feasible_region"])
            # Region must not be a single collapsed point when reference span is wide.
            ref = e["feasible_region"]
            span = ref["f_au_max"] - ref["f_au_min"] + ref["f_ag_max"] - ref["f_ag_min"]
            if span > 1e-3:
                gspan = (
                    g["feasible_region"]["f_au_max"]
                    - g["feasible_region"]["f_au_min"]
                    + g["feasible_region"]["f_ag_max"]
                    - g["feasible_region"]["f_ag_min"]
                )
                assert gspan > 1e-3


def test_inconsistent_list():
    """inconsistent-coins.json lists exactly the reference-inconsistent coin ids."""
    expected = build_products(APP)
    got = json.loads((OUTPUT / "inconsistent-coins.json").read_text(encoding="utf-8"))
    assert got["coin_ids"] == expected["inconsistent"]
    assert "BAD-401" in got["coin_ids"]


def test_wide_band_not_error():
    """WIDE-301 with large density sigma remains feasible or density-consistent, never insufficient_data."""
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    row = next(c for c in got["coins"] if c["coin_id"] == "WIDE-301")
    assert row["status"] in ("feasible", "density_only")
    assert row["feasible_region"] is not None


def test_missing_xrf_density_only():
    """MISS-501 without XRF fractions is density_only with a density-derived region."""
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    row = next(c for c in got["coins"] if c["coin_id"] == "MISS-501")
    assert row["status"] == "density_only"
    assert row["feasible_region"] is not None


def test_missing_density_insufficient():
    """MISS-502 without density is insufficient_data with missing_density reason."""
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    row = next(c for c in got["coins"] if c["coin_id"] == "MISS-502")
    assert row["status"] == "insufficient_data"
    assert row["reason"] == "missing_density"


def test_per_coin_enrichment_models_differ():
    """AG-101 and AG-102 share measurements but use different enrichment models → distinct deltas in trace."""
    trace = json.loads((OUTPUT / "derivation-trace.json").read_text(encoding="utf-8"))
    a = next(c for c in trace["coins"] if c["coin_id"] == "AG-101")
    b = next(c for c in trace["coins"] if c["coin_id"] == "AG-102")
    assert a["xrf_bound"]["model_id"] == "burial_short"
    assert b["xrf_bound"]["model_id"] == "burial_long"
    assert a["xrf_bound"]["delta"] != b["xrf_bound"]["delta"]


def test_derivation_trace_matches_reference():
    """derivation-trace.json density_band, xrf_bound, and intersection_point_count match the independent reference."""
    expected = build_products(APP)
    trace = json.loads((OUTPUT / "derivation-trace.json").read_text(encoding="utf-8"))
    assert trace["schema_version"] == 1
    assert [c["coin_id"] for c in trace["coins"]] == [c["coin_id"] for c in expected["coins"]]
    for e, g in zip(expected["coins"], trace["coins"]):
        assert e["coin_id"] == g["coin_id"]
        assert g["intersection_point_count"] == e["intersection_point_count"]
        if e["density_band"] is None:
            assert g["density_band"] is None
        else:
            assert g["density_band"]["point_count"] == e["density_band"]["point_count"]
            _region_close(e["density_band"], g["density_band"])
        if e["xrf_bound"] is None:
            assert g["xrf_bound"] is None
        else:
            for k in (
                "f_au_min",
                "f_au_max",
                "f_ag_min",
                "f_ag_max",
                "f_cu_min",
                "f_cu_max",
                "delta",
            ):
                assert abs(float(g["xrf_bound"][k]) - float(e["xrf_bound"][k])) < TOL, (
                    e["coin_id"],
                    k,
                    g["xrf_bound"][k],
                    e["xrf_bound"][k],
                )
            assert g["xrf_bound"]["model_id"] == e["xrf_bound"]["model_id"]


def test_export_fails_when_ledger_missing():
    """export with a snapshot but no assay-ledger.jsonl must fail and must not republish outputs."""
    reset_io()
    run_ledger("analyze")
    ledger = STATE / "assay-ledger.jsonl"
    assert ledger.is_file()
    ledger.unlink()
    for name in (
        "composition-results.json",
        "derivation-trace.json",
        "inconsistent-coins.json",
        "audit.json",
    ):
        (OUTPUT / name).unlink()
    cp = run_ledger("export", check=False)
    assert cp.returncode != 0
    assert not (OUTPUT / "composition-results.json").is_file()
    reset_io()
    run_ledger("analyze")


def test_export_fails_when_assay_bind_mismatched():
    """export must fail when snapshot assay_bind no longer matches the ledger entry."""
    reset_io()
    run_ledger("analyze")
    snap_path = STATE / "assay-snapshot.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    snap["assay_bind"] = "0" * 64
    snap_path.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    for name in (
        "composition-results.json",
        "derivation-trace.json",
        "inconsistent-coins.json",
        "audit.json",
    ):
        (OUTPUT / name).unlink()
    cp = run_ledger("export", check=False)
    assert cp.returncode != 0
    assert not (OUTPUT / "composition-results.json").is_file()
    reset_io()
    run_ledger("analyze")


def test_boundary_coin_handled():
    """EDGE-601 with surface copper at zero is classified without crash and has structured output."""
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    row = next(c for c in got["coins"] if c["coin_id"] == "EDGE-601")
    assert row["status"] in ("feasible", "inconsistent", "density_only")
    assert "coin_id" in row


def test_audit_counts():
    """Audit counters match reference tallies and bind fields are present."""
    expected = build_products(APP)
    audit = json.loads((OUTPUT / "audit.json").read_text(encoding="utf-8"))
    assert audit["coin_count"] == len(expected["coins"])
    assert audit["feasible_count"] == expected["feasible_count"]
    assert audit["inconsistent_count"] == expected["inconsistent_count"]
    assert audit["density_only_count"] == expected["density_only_count"]
    assert audit["insufficient_count"] == expected["insufficient_count"]
    assert isinstance(audit["assay_bind"], str) and len(audit["assay_bind"]) == 64
    assert audit["ingest_seq"] >= 1


def test_export_without_snapshot_exits_2():
    """export without a snapshot exits 2 and does not invent outputs from data alone."""
    reset_io()
    cp = run_ledger("export", check=False)
    assert cp.returncode == 2


def test_export_from_snapshot_only():
    """export regenerates outputs from snapshot without requiring a fresh analyze."""
    reset_io()
    run_ledger("analyze")
    # Remove data so a dishonest re-read would fail; export must use snapshot only.
    coins_backup = (DATA / "coins.json").read_text(encoding="utf-8")
    try:
        (DATA / "coins.json").write_text("{}", encoding="utf-8")
        for name in (
            "composition-results.json",
            "derivation-trace.json",
            "inconsistent-coins.json",
            "audit.json",
        ):
            (OUTPUT / name).unlink()
        run_ledger("export")
        got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
        assert len(got["coins"]) >= 1
    finally:
        (DATA / "coins.json").write_text(coins_backup, encoding="utf-8")


def test_check_coin_prints_detail():
    """check-coin prints JSON detail for the requested coin id."""
    reset_io()
    cp = run_ledger("check-coin", "AG-101")
    detail = json.loads(cp.stdout)
    assert detail["coin_id"] == "AG-101"
    assert "status" in detail


def test_relative_config_override_fails():
    """Relative TB3_ASSAY_CONFIG path must fail closed."""
    cp = run_ledger("analyze", check=False, env={"TB3_ASSAY_CONFIG": "data/assay-config.json"})
    assert cp.returncode != 0


def test_hidden_fixture_catalog():
    """Hidden verifier fixture catalog statuses match independent reference under TB3_COINS."""
    if not FIXTURES.exists():
        pytest.skip("no hidden fixtures")
    fixture_coins = FIXTURES / "coins-hidden.json"
    if not fixture_coins.is_file():
        pytest.skip("no hidden coins fixture")
    reset_io()
    run_ledger(
        "analyze",
        env={"TB3_COINS": str(fixture_coins)},
    )
    cfg = load_json(APP / "data" / "assay-config.json")
    metals = load_json(APP / "data" / "metal-densities.json")
    models = load_json(APP / "data" / "enrichment-models.json")
    catalog = load_json(fixture_coins)
    expected = [evaluate_coin(c, metals, models, cfg) for c in catalog["coins"]]
    expected.sort(key=lambda r: r["coin_id"])
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    assert [c["coin_id"] for c in got["coins"]] == [c["coin_id"] for c in expected]
    for e, g in zip(expected, got["coins"]):
        assert e["status"] == g["status"]
        if e["feasible_region"] is not None:
            _region_close(e["feasible_region"], g["feasible_region"])
    # Restore default catalog outputs for any later tests that share module state.
    reset_io()
    run_ledger("analyze")


def test_nonideal_mixing_applied():
    """AU-201 nonideal kappa path matches reference status and region."""
    reset_io()
    run_ledger("analyze")
    expected = build_products(APP)
    exp = next(c for c in expected["coins"] if c["coin_id"] == "AU-201")
    got = json.loads((OUTPUT / "composition-results.json").read_text(encoding="utf-8"))
    g = next(c for c in got["coins"] if c["coin_id"] == "AU-201")
    assert g["status"] == exp["status"]
    if exp["feasible_region"] is not None:
        _region_close(exp["feasible_region"], g["feasible_region"])
