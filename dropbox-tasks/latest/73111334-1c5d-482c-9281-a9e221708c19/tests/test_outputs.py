"""Verifier for fog-of-war-memory-budget-build schema_version 3."""

import importlib.util
import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/session_ledger.json")
STATE = ENV / "state"
RECOVER = ENV / "docs" / "recover_k.txt"
REF_PATH = Path(__file__).parent / "reference_model.py"


def _load_ref():
    spec = importlib.util.spec_from_file_location("reference_model", REF_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


REF = _load_ref()


def _emit(ticks: str = "12:0") -> dict:
    if OUT.exists():
        OUT.unlink()
    proc = subprocess.run(
        ["/app/bin/k7", "--suite", "g2", "--ticks", ticks, "--emit", str(OUT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(OUT.read_text())


def _reset_state() -> None:
    if STATE.exists():
        shutil.rmtree(STATE)
    STATE.mkdir(parents=True, exist_ok=True)


def _recover_once() -> None:
    for line in RECOVER.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            proc = subprocess.run(["bash", "-lc", line], capture_output=True, text=True, check=False)
            assert proc.returncode == 0, proc.stderr + proc.stdout


@contextmanager
def mutate(path: Path, mutate_fn):
    original = path.read_text()
    path.write_text(mutate_fn(original))
    try:
        yield
    finally:
        path.write_text(original)


def _run_and_read() -> dict:
    proc = subprocess.run(
        ["bash", str(ENV / "scripts/forge_all.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return _emit()


def _expected_source_refs(scenario_id: str, mode: str) -> list[str]:
    return sorted(
        {
            f"cases/g2/{scenario_id}.json",
            f"specs_r/{mode}.toml",
            "docs/field_rules.md",
            "docs/api.md",
            "docs/lex_k.tsv",
        }
    )


@pytest.fixture(scope="module", autouse=True)
def reset_before_module():
    """Reset grader state before and after the module so recovery tests start clean."""
    _reset_state()
    yield
    _reset_state()


@pytest.fixture(scope="module")
def ledger():
    """Build the workspace once and return the certified schema_version 3 ledger."""
    return _run_and_read()


def _run_ref(ledger_doc: dict, scenario_id: str, **kwargs) -> dict:
    sc = REF.load_scenario(scenario_id)
    return REF.simulate(sc, ledger_doc["ticks"], **kwargs)


def test_v01_schema(ledger):
    """Require schema_version 3 with all top-level and per-run v3 provenance fields."""
    assert ledger["schema_version"] == 3
    for key in (
        "suite",
        "ticks",
        "peak_resident_bytes",
        "resident_cap_bytes",
        "footprint_band",
        "runs",
        "orchestrator_phases",
        "worker_phases",
        "source_digest",
        "phase_digest",
        "ledger_digest",
        "plane_trace_digest",
        "cadence_digest",
        "pool_trace_digest",
        "scenario_digest",
    ):
        assert key in ledger
    for run in ledger["runs"]:
        for key in ("plane_trace", "cadence_trace_v3", "pool_trace", "source_refs", "run_v3_digest"):
            assert key in run


def test_v02_discovery_and_ticks(ledger):
    """Require all g2 scenarios discovered and ticks expanded via r0 tick_scale (12:0 -> 120)."""
    emitted = sorted(r["scenario_id"] for r in ledger["runs"])
    assert emitted == REF.discover_case_ids("g2")
    assert emitted == ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]
    assert ledger["ticks"] == 120


def test_v03_band(ledger):
    """Require peak resident bytes within the configured cap."""
    assert ledger["footprint_band"] == "WITHIN"
    assert ledger["peak_resident_bytes"] <= ledger["resident_cap_bytes"]


def test_v04_plane_separation(ledger):
    """Require dual-plane separation: explored stays distinct from tick-local sensor."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c2")
    assert run["bitplane_digests"]["plane_a"] != run["bitplane_digests"]["plane_b"]
    assert run["explored_count"] >= run["sensor_count"]


def test_v05_counts_match_reference(ledger):
    """Require explored/sensor/stale counts to match the independent reference model."""
    for run in ledger["runs"]:
        ref = _run_ref(ledger, run["scenario_id"])
        assert run["explored_count"] == ref["explored_count"]
        assert run["sensor_count"] == ref["sensor_count"]
        assert run["stale_count"] == ref["stale_count"]


def test_v06_alias_planes_rejected(ledger):
    """Reject plane replay that overwrites explored with lit instead of merging monotonically."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c2")
    broken = _run_ref(ledger, "c2", fixed_pack=False)
    assert run["plane_delta_digest"] != broken["plane_delta_digest"] or run["explored_count"] != broken[
        "explored_count"
    ]


def test_v07_grid_geometry_width_not_four(ledger):
    """Require non-four-column geometry (c1 2x2 and c7 5x4) to match reference lit masks."""
    for cid in ("c1", "c7"):
        run = next(r for r in ledger["runs"] if r["scenario_id"] == cid)
        ref = _run_ref(ledger, cid)
        bad = _run_ref(ledger, cid, fixed_geometry=False)
        assert run["plane_trace"] == ref["plane_trace"]
        assert run["explored_count"] != bad["explored_count"] or run["plane_trace"] != bad["plane_trace"]


def test_v08_scenario_grid_fields():
    """Require every fixture to declare grid_width/grid_height with slots == width*height."""
    for path in sorted((ENV / "cases/g2").glob("*.json")):
        sc = json.loads(path.read_text())
        assert "grid_width" in sc and "grid_height" in sc
        assert sc["slots"] == sc["grid_width"] * sc["grid_height"]
        for obs in sc.get("observers", []):
            assert obs["cx"] < sc["grid_width"]
            assert obs["cy"] < sc["grid_height"]


def test_v09_phase_half_open(ledger):
    """Require half-open phase windows; inclusive until_tick boundaries must diverge."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c2")
    ref = _run_ref(ledger, "c2")
    bad = _run_ref(ledger, "c2", fixed_phases=False)
    assert run["plane_trace"] == ref["plane_trace"]
    # Inclusive vs half-open differs around boundary ticks for multi-phase cases with reach changes.
    assert run["fade_checksum"] == ref["fade_checksum"]
    assert ref["plane_trace"] != bad["plane_trace"] or ref["cadence_trace"] != bad["cadence_trace"]


def test_v10_cadence_phase_aware(ledger):
    """Require mode decay_phase gating (r1 phase=2) rather than decay-every-tick."""
    for cid in ("c3", "c6"):
        run = next(r for r in ledger["runs"] if r["scenario_id"] == cid)
        ref = _run_ref(ledger, cid)
        bad = _run_ref(ledger, cid, fixed_tick=False, every_tick_decay=True)
        assert run["cadence_trace"] == ref["cadence_trace"]
        assert run["cadence_trace_v3"] == ref["cadence_trace_v3"]
        assert run["cadence_trace_v3"] != bad["cadence_trace_v3"]


def test_v11_mode_fields():
    """Require mode specs to expose decay_phase and pool byte fields used by accounting."""
    r0 = REF.load_mode("r0")
    r1 = REF.load_mode("r1")
    assert r0["decay_modulus"] == 4 and r0["decay_phase"] == 0
    assert r1["decay_modulus"] == 5 and r1["decay_phase"] == 2
    assert r0["group_header_bytes"] == 32 and r0["observer_metadata_bytes"] == 16
    assert r1["group_header_bytes"] == 32 and r1["observer_metadata_bytes"] == 16


def test_v12_ally_pool_copies_and_bytes(ledger):
    """Require canonical ally pools with copies=1 and cumulative header/metadata footprint."""
    c3 = next(r for r in ledger["runs"] if r["scenario_id"] == "c3")
    ref = _run_ref(ledger, "c3")
    assert c3["merge_lineage"]
    assert all(row["copies"] == 1 for row in c3["merge_lineage"])
    assert c3["merge_lineage"] == ref["lineage"]
    assert c3["resident_trace"] == ref["resident_trace"]
    assert c3["resident_trace"][-1] == ref["resident_trace"][-1]
    bad = _run_ref(ledger, "c3", fixed_merge=False)
    assert c3["peak_bytes"] != bad["peak_bytes"] or c3["merge_lineage"] != bad["lineage"]


def test_v13_c8_triple_and_c7_multi_group(ledger):
    """Require c8 triple-observer and c7 multi-group pools to stay within cap with copies=1."""
    c8 = next(r for r in ledger["runs"] if r["scenario_id"] == "c8")
    c7 = next(r for r in ledger["runs"] if r["scenario_id"] == "c7")
    assert len(c8["merge_lineage"]) == 1
    assert c8["merge_lineage"][0]["copies"] == 1
    assert len(c8["merge_lineage"][0]["group"]) == 3
    assert c8["resident_trace"] == _run_ref(ledger, "c8")["resident_trace"]
    handles = {row["handle"] for row in c7["merge_lineage"]}
    assert len(handles) >= 2
    assert all(row["copies"] == 1 for row in c7["merge_lineage"])
    assert c7["footprint_band"] == "WITHIN"


def test_v14_pool_trace_sorted_observers(ledger):
    """Require pool_trace observer lists to use canonical sorted ids."""
    for run in ledger["runs"]:
        ref = _run_ref(ledger, run["scenario_id"])
        assert run["pool_trace"] == ref["pool_trace"]


def test_v15_tick_parse_ok_and_reject():
    """Require strict tick parsing: valid HIGH:LOW and plain ints; reject malformed and overflow args."""
    ok = subprocess.run(
        ["/app/bin/k7", "--suite", "g2", "--ticks", "12:0", "--emit", str(OUT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0
    doc = json.loads(OUT.read_text())
    assert doc["ticks"] == 120

    plain = subprocess.run(
        ["/app/bin/k7", "--suite", "g2", "--ticks", "7", "--emit", str(OUT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert plain.returncode == 0
    assert json.loads(OUT.read_text())["ticks"] == 7

    # With r0 tick_scale=10, HIGH*scale overflows u64 for these values.
    overflow_cases = ("1844674407370955162:0", "9223372036854775808:1", "18446744073709551615:0")
    for bad in (":1", "1:", "a:b", "1:2:3", "", *overflow_cases):
        proc = subprocess.run(
            ["/app/bin/k7", "--suite", "g2", "--ticks", bad, "--emit", str(OUT)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, bad
        assert proc.stderr.strip() != "", bad


def test_v16_ledger_includes_v3_provenance(ledger):
    """Require ledger_digest to fold v3 digests; legacy run-pair-only fold must not match."""
    assert ledger["ledger_digest"] == REF.ledger_digest(ledger)
    assert ledger["ledger_digest"] != REF.ledger_digest_legacy(ledger)


def test_v17_top_v3_digests(ledger):
    """Require top-level plane/cadence/pool/scenario digests to match reference aggregation."""
    assert ledger["plane_trace_digest"] == REF.trace_digest(ledger, "plane_trace")
    assert ledger["cadence_digest"] == REF.trace_digest(ledger, "cadence_trace_v3")
    assert ledger["pool_trace_digest"] == REF.trace_digest(ledger, "pool_trace")
    assert ledger["scenario_digest"] == REF.scenario_digest("g2")
    assert ledger["source_digest"] == REF.source_digest("g2")


def test_v18_run_digests(ledger):
    """Require each run_digest and run_v3_digest to match reference formulas."""
    for run in ledger["runs"]:
        assert run["run_digest"] == REF.run_digest(run)
        assert run["run_v3_digest"] == REF.run_v3_digest(run)


def test_v19_recovery_epochs_0_1_2(ledger):
    """Require recovery_epoch file semantics for epochs 0, then 1, then 2 after successive recovers."""
    assert all(r["recovery_epoch"] == 0 for r in ledger["runs"])
    epoch_file = STATE / "recovery_epoch"
    assert not epoch_file.exists() or epoch_file.read_text().strip() in ("", "0")

    subprocess.run(["bash", str(ENV / "migrations/purge_k.sh")], capture_output=True, text=True, check=False)
    _recover_once()
    post1 = _emit()
    assert all(r["recovery_epoch"] == 1 for r in post1["runs"])
    assert epoch_file.read_text().strip() == "1"

    _recover_once()
    post2 = _emit()
    assert all(r["recovery_epoch"] == 2 for r in post2["runs"])
    assert epoch_file.read_text().strip() == "2"
    assert not (STATE / "recovered.flag").exists()
    _reset_state()


def test_v20_probe_banner():
    """Require probe banner CHUNK_BAND=GREEN after kernels satisfy the contract."""
    probe = subprocess.run(
        ["/app/bin/k7", "probe", "--suite", "g2"], capture_output=True, text=True, check=False
    )
    assert "CHUNK_BAND=GREEN" in probe.stdout


def test_v21_plane_and_cadence_formulas(ledger):
    """Require plane_trace and cadence_trace_v3 for every scenario to match the reference."""
    for run in ledger["runs"]:
        ref = _run_ref(ledger, run["scenario_id"])
        assert run["plane_trace"] == ref["plane_trace"]
        assert run["cadence_trace_v3"] == ref["cadence_trace_v3"]
        assert run["cadence_trace"] == ref["cadence_trace"]
        assert run["fade_checksum"] == ref["fade_checksum"]


def test_v22_c5_multiphase_stale(ledger):
    """Require c5 multi-phase coverage to produce explored > sensor with nonzero stale."""
    c5 = next(r for r in ledger["runs"] if r["scenario_id"] == "c5")
    assert c5["bitplane_digests"]["plane_a"] != c5["bitplane_digests"]["plane_b"]
    assert c5["explored_count"] > c5["sensor_count"]
    assert c5["stale_count"] > 0


def test_v23_c6_r1_differs_from_c2(ledger):
    """Require c6 (r1 modulus/phase/fade) fade_checksum to differ from c2 (r0)."""
    c6 = next(r for r in ledger["runs"] if r["scenario_id"] == "c6")
    c2 = next(r for r in ledger["runs"] if r["scenario_id"] == "c2")
    assert c6["fade_checksum"] != c2["fade_checksum"]


def test_v24_source_refs_exact_set(ledger):
    """Require each run source_refs to equal the exact sorted, deduplicated contract set."""
    for run in ledger["runs"]:
        sc = REF.load_scenario(run["scenario_id"])
        expected = _expected_source_refs(run["scenario_id"], sc["mode"])
        assert run["source_refs"] == expected
        assert run["source_refs"] == sorted(set(run["source_refs"]))


def test_v25_idempotent_emit(ledger):
    """Require a second emit to reproduce the same ledger_digest."""
    assert _emit()["ledger_digest"] == ledger["ledger_digest"]


def test_v26_dynamic_c9_discovered():
    """Require newly added c9.json to be discovered dynamically."""
    c9 = ENV / "cases/g2/c9.json"
    c5 = ENV / "cases/g2/c5.json"
    raw = c5.read_text().replace('"c5"', '"c9"')
    c9.write_text(raw)
    try:
        doc = _run_and_read()
        assert "c9" in sorted(r["scenario_id"] for r in doc["runs"])
    finally:
        if c9.exists():
            c9.unlink()


def test_v27_static_v2_rejected():
    """Reject a hand-written schema_version 2 ledger in favor of a fresh v3 emit."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"schema_version": 2, "runs": []}))
    doc = _emit()
    assert doc["schema_version"] == 3


def test_v28_ablate_pack(ledger):
    """Reject implementations whose plane replay matches the aliased-plane ablation."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c2")
    bad = _run_ref(ledger, "c2", fixed_pack=False)
    assert run["plane_delta_digest"] != bad["plane_delta_digest"]


def test_v29_ablate_tick(ledger):
    """Reject implementations whose cadence matches every-tick decay ablation."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c6")
    bad = _run_ref(ledger, "c6", fixed_tick=False, every_tick_decay=True)
    assert run["cadence_trace_v3"] != bad["cadence_trace_v3"]


def test_v30_ablate_merge(ledger):
    """Reject implementations whose pool accounting matches copies=len(group) ablation."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c3")
    bad = _run_ref(ledger, "c3", fixed_merge=False)
    assert run["peak_bytes"] != bad["peak_bytes"] or run["merge_lineage"] != bad["lineage"]


def test_v31_ablate_geometry(ledger):
    """Reject implementations that hardcode grid width 4 on the 5-column c7 fixture."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c7")
    bad = _run_ref(ledger, "c7", fixed_geometry=False)
    assert run["explored_count"] != bad["explored_count"] or run["plane_trace"] != bad["plane_trace"]


def test_v32_ablate_missing_traces(ledger):
    """Reject emptied v3 traces because aggregate digests would no longer verify."""
    c = dict(ledger)
    c["runs"] = [dict(r) for r in ledger["runs"]]
    c["runs"][0]["plane_trace"] = []
    assert REF.trace_digest(c, "plane_trace") != ledger["plane_trace_digest"]
    c2 = dict(ledger)
    c2["runs"] = [dict(r) for r in ledger["runs"]]
    c2["runs"][0]["cadence_trace_v3"] = []
    assert REF.trace_digest(c2, "cadence_trace_v3") != ledger["cadence_digest"]
    c3 = dict(ledger)
    c3["runs"] = [dict(r) for r in ledger["runs"]]
    idx = next(i for i, r in enumerate(c3["runs"]) if r["pool_trace"])
    c3["runs"][idx]["pool_trace"] = []
    assert REF.trace_digest(c3, "pool_trace") != ledger["pool_trace_digest"]


def test_v33_mutate_c5_plane(ledger):
    """Require plane_trace_digest to change when c5 slot geometry is mutated."""
    path = ENV / "cases/g2/c5.json"
    with mutate(
        path,
        lambda t: t.replace('"slots": 12', '"slots": 16').replace('"grid_height": 3', '"grid_height": 4'),
    ):
        doc = _run_and_read()
        assert doc["plane_trace_digest"] != ledger["plane_trace_digest"]


def test_v34_mutate_r1_cadence(ledger):
    """Require cadence_digest to change when r1 fade_start is mutated."""
    path = ENV / "specs_r/r1.toml"
    with mutate(path, lambda t: t.replace("fade_start = 8", "fade_start = 9")):
        doc = _run_and_read()
        assert doc["cadence_digest"] != ledger["cadence_digest"]


def test_v35_mutate_c7_pool(ledger):
    """Require pool_trace_digest to change when c7 group membership is mutated."""
    path = ENV / "cases/g2/c7.json"
    with mutate(path, lambda t: t.replace("[52, 53, 54]", "[52, 53]")):
        doc = _run_and_read()
        assert doc["pool_trace_digest"] != ledger["pool_trace_digest"]


def test_v36_mutate_spec_scenario_digest(ledger):
    """Require scenario_digest to change when r0 resident_cap is mutated."""
    path = ENV / "specs_r/r0.toml"
    with mutate(path, lambda t: t.replace("resident_cap = 8192", "resident_cap = 9000")):
        doc = _run_and_read()
        assert doc["scenario_digest"] != ledger["scenario_digest"]


def test_v37_decay_trace_tail(ledger):
    """Require c2 decay_trace to retain the eight-entry tail."""
    run = next(r for r in ledger["runs"] if r["scenario_id"] == "c2")
    assert len(run["decay_trace"]) == 8
    assert run["decay_trace"] == _run_ref(ledger, "c2")["decay_trace"]


def test_v38_dynamic_reordered_ally_group(ledger):
    """Require reordered ally observer ids to canonicalize to the same pool handle/bytes."""
    path = ENV / "cases/g2/c3.json"
    with mutate(path, lambda t: t.replace("[10, 11]", "[11, 10]")):
        doc = _run_and_read()
        c3 = next(r for r in doc["runs"] if r["scenario_id"] == "c3")
        assert c3["merge_lineage"][0]["group"] == [10, 11]
        assert c3["merge_lineage"][0]["handle"] == 10
        assert c3["merge_lineage"][0]["copies"] == 1


def test_v39_dynamic_combined_geometry_phase_cadence_pool():
    """Require a hidden fixture combining width-3 geometry, phase shift, r1 cadence, and ally pooling."""
    path = ENV / "cases/g2/c9.json"
    fixture = {
        "id": "c9",
        "mode": "r1",
        "slots": 9,
        "grid_width": 3,
        "grid_height": 3,
        "observers": [
            {"oid": 90, "cx": 1, "cy": 1, "reach": 1},
            {"oid": 91, "cx": 0, "cy": 2, "reach": 1},
        ],
        "observer_phases": [
            {"until_tick": 40, "observers": [{"oid": 90, "cx": 0, "cy": 0, "reach": 2}]},
            {"until_tick": 120, "observers": [{"oid": 90, "cx": 2, "cy": 2, "reach": 1}]},
        ],
        "ally_groups": [[90, 91]],
    }
    path.write_text(json.dumps(fixture, indent=2))
    try:
        doc = _run_and_read()
        run = next(r for r in doc["runs"] if r["scenario_id"] == "c9")
        ref = _run_ref(doc, "c9")
        assert run["explored_count"] == ref["explored_count"]
        assert run["sensor_count"] == ref["sensor_count"]
        assert run["cadence_trace"] == ref["cadence_trace"]
        assert run["plane_trace"] == ref["plane_trace"]
        assert run["merge_lineage"] == ref["lineage"]
        assert run["pool_trace"] == ref["pool_trace"]
        assert run["merge_lineage"] and run["merge_lineage"][0]["copies"] == 1
        assert run["merge_lineage"][0]["handle"] == 90
        # Width-3 trap: hardcoding width 4 must diverge.
        bad = _run_ref(doc, "c9", fixed_geometry=False)
        assert run["explored_count"] != bad["explored_count"] or run["plane_trace"] != bad["plane_trace"]
    finally:
        if path.exists():
            path.unlink()


def test_v40_recovery_malformed_epoch_emit():
    """Require empty/non-decimal recovery_epoch files to stamp emit epoch 0 without rewriting."""
    _reset_state()
    epoch_file = STATE / "recovery_epoch"

    epoch_file.write_text("")
    empty_doc = _emit()
    assert all(r["recovery_epoch"] == 0 for r in empty_doc["runs"])
    assert epoch_file.read_text() == ""

    epoch_file.write_text("not-a-number\n")
    bad_doc = _emit()
    assert all(r["recovery_epoch"] == 0 for r in bad_doc["runs"])
    assert epoch_file.read_text() == "not-a-number\n"
    _reset_state()


def test_v41_recovery_hook_rejects_non_decimal():
    """Require the recovery hook to fail non-zero on non-decimal epoch content."""
    _reset_state()
    epoch_file = STATE / "recovery_epoch"
    epoch_file.write_text("abc")
    failed = False
    for line in RECOVER.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            proc = subprocess.run(["bash", "-lc", line], capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                failed = True
                assert proc.stderr.strip() != ""
                break
    assert failed
    assert epoch_file.read_text().strip() == "abc"
    _reset_state()


def test_v42_non_increasing_phase_boundaries():
    """Require duplicate/non-increasing until_tick phases to yield no active observers."""
    path = ENV / "cases/g2/c9.json"
    fixture = {
        "id": "c9",
        "mode": "r0",
        "slots": 4,
        "grid_width": 2,
        "grid_height": 2,
        "observers": [{"oid": 1, "cx": 0, "cy": 0, "reach": 4}],
        "observer_phases": [
            {"until_tick": 80, "observers": [{"oid": 1, "cx": 0, "cy": 0, "reach": 4}]},
            {"until_tick": 80, "observers": [{"oid": 1, "cx": 1, "cy": 1, "reach": 1}]},
        ],
        "ally_groups": [],
    }
    path.write_text(json.dumps(fixture, indent=2))
    try:
        doc = _run_and_read()
        run = next(r for r in doc["runs"] if r["scenario_id"] == "c9")
        ref = _run_ref(doc, "c9")
        assert run["explored_count"] == 0
        assert run["sensor_count"] == 0
        assert run["plane_trace"] == ref["plane_trace"]
        assert REF.phases_valid(fixture) is False
    finally:
        if path.exists():
            path.unlink()


def test_v43_zero_decay_modulus_no_automatic_fade():
    """Require decay_modulus=0 to disable automatic fade (all cadence step markers stay 0)."""
    path = ENV / "specs_r/r0.toml"
    with mutate(path, lambda t: t.replace("decay_modulus = 4", "decay_modulus = 0")):
        doc = _run_and_read()
        c2 = next(r for r in doc["runs"] if r["scenario_id"] == "c2")
        ref = _run_ref(doc, "c2")
        assert c2["cadence_trace"] == ref["cadence_trace"]
        assert c2["cadence_trace_v3"] == ref["cadence_trace_v3"]
        assert all(":step:0:" in row for row in c2["cadence_trace"])
        assert all(":decay:0:" in row for row in c2["cadence_trace_v3"])


def test_v44_duplicate_equivalent_ally_groups():
    """Require reordered duplicate ally groups to share one allocation (idempotent pool)."""
    path = ENV / "cases/g2/c3.json"
    original = path.read_text()
    try:
        sc = json.loads(original)
        sc["ally_groups"] = [[10, 11], [11, 10]]
        path.write_text(json.dumps(sc, indent=2) + "\n")
        doc = _run_and_read()
        c3 = next(r for r in doc["runs"] if r["scenario_id"] == "c3")
        ref = _run_ref(doc, "c3")
        assert len(c3["merge_lineage"]) == 1
        assert c3["merge_lineage"][0]["group"] == [10, 11]
        assert c3["merge_lineage"][0]["copies"] == 1
        assert c3["merge_lineage"][0]["handle"] == 10
        assert c3["peak_bytes"] == ref["peak_bytes"]
        assert c3["resident_trace"] == ref["resident_trace"]
        assert any(row.startswith("group:0:") for row in c3["pool_trace"])
        assert any(row.startswith("group:1:") for row in c3["pool_trace"])
    finally:
        path.write_text(original)
