"""Verifier for qcl_emit.json from the quantization calibration driver."""

import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path("/app")
ENV_ROOT = ROOT / "environment"
OUTPUT = ROOT / "output" / "qcl_emit.json"
DRIVER = ["ruby", "environment/qcl/drive_qcl.rb", "--matrix-all"]
ROW_CODEC = ENV_ROOT / "util" / "row_codec.rb"
POISON = ["ruby", "-r", "/app/environment/f5/scratch_arena.rb", "-e", "F5::ScratchArena.poison!"]
RECOVERY = ["ruby", "-r", "/app/environment/f5/scratch_arena.rb", "-e", "F5::ScratchArena.clear!"]
MODES = ["fp16_baseline", "int8_strict", "mixed_edge"]
CASES = ["sage", "opal", "birch", "rowan"]


def ruby_row_digest(case_id, mode_id, layer_id, scale_u32, stat_min, stat_max, replay_tag):
    script = (
        f"require '{ROW_CODEC}'; "
        "puts Util::RowCodec.row_digest("
        f"{case_id!r}, {mode_id!r}, {layer_id!r}, {scale_u32}, "
        f"{stat_min}, {stat_max}, {replay_tag!r})"
    )
    proc = subprocess.run(
        ["ruby", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def run_driver():
    subprocess.run(DRIVER, cwd=ROOT, check=True, capture_output=True, text=True)


def load_emit():
    run_driver()
    assert OUTPUT.exists(), "qcl_emit.json missing after drive_qcl"
    return json.loads(OUTPUT.read_text())


def rows_for(emit, case_id, mode_id):
    return [r for r in emit["rows"] if r["case_id"] == case_id and r["mode_id"] == mode_id]


def case_values(case_id):
    if case_id == "sage":
        source = ENV_ROOT / "h5" / "w1" / "sag_a.ndjson"
        limit = None
    elif case_id == "opal":
        source = ENV_ROOT / "h5" / "w1" / "opa_b.ndjson"
        limit = None
    else:
        source = ENV_ROOT / "h5" / "w1" / "sag_a.ndjson"
        limit = 3
    rows = []
    with source.open() as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    if limit is not None:
        rows = rows[:limit]
    return [float(v) for row in rows for v in row.get("vals", [])]


def policy_table():
    return tomllib.loads((ENV_ROOT / "h5" / "x7" / "policy_table.toml").read_text())


def mode_bounds(mode_id):
    table = policy_table()
    return table.get(mode_id, table.get("default", {"lo": -1.0, "hi": 1.0}))


def clamp(value, lo, hi):
    return min(max(float(value), float(lo)), float(hi))


def expected_stats(case_id, mode_id):
    bounds = mode_bounds(mode_id)
    vals = [clamp(v, bounds["lo"], bounds["hi"]) for v in case_values(case_id)]
    return min(vals), max(vals)


def load_shard(case_id):
    shard_name = "shard_rowan.toml" if case_id == "rowan" else "shard_birch.toml"
    return tomllib.loads((ENV_ROOT / "h5" / "w2" / shard_name).read_text())


def merged_layer_bounds(case_id, mode_id, layer_id):
    bounds = dict(mode_bounds(mode_id))
    layer = load_shard(case_id).get("layers", {}).get(layer_id, {})
    if "lo" in layer:
        bounds["lo"] = layer["lo"]
    if "hi" in layer:
        bounds["hi"] = layer["hi"]
    return bounds


def expected_scale(case_id, mode_id, layer_id):
    stat_min, stat_max = expected_stats(case_id, mode_id)
    mid = (stat_min + stat_max) / 2.0
    bounds = merged_layer_bounds(case_id, mode_id, layer_id)
    clipped = [round(clamp(v, bounds["lo"], bounds["hi"]), 3) for v in (stat_min, stat_max, mid)]
    base = abs(sum(round(v * 1000) for v in clipped))
    offset = sum(layer_id.encode())
    if mode_id == "int8_strict":
        return (base % 2000) + 256 + offset
    if mode_id == "mixed_edge":
        return (base % 3000) + 512 + (offset * 2)
    return (base % 1500) + 128 + offset



def write_dynamic_qz_case():
    """Create a verifier-only pool case with a new mode and explicit source/shard."""
    source = ENV_ROOT / "h5" / "w1" / "dyn_zeta.ndjson"
    shard = ENV_ROOT / "h5" / "w2" / "shard_dyn_zeta.toml"
    pool = ENV_ROOT / "h5" / "pool" / "QZ-zeta-dynamic.json"
    policy = ENV_ROOT / "h5" / "x7" / "policy_table.toml"
    source.write_text(
        '\n'.join([
            json.dumps({"wave": 0, "vals": [-1.2, -0.125, 0.875]}),
            json.dumps({"wave": 1, "vals": [0.3333, 0.999, -0.4444]}),
        ])
        + "\n"
    )
    shard.write_text(
        "parent_shard = \"dyn-zeta\"\n"
        "parent_scale = 4096\n\n"
        "[layers.A2]\nlo = -0.2\nhi = 0.35\n\n"
        "[layers.Z9]\nlo = -0.125\nhi = 0.125\n"
    )
    if "[zz_micro]" not in policy.read_text():
        policy.write_text(policy.read_text() + "\n[zz_micro]\nlo = -0.25\nhi = 0.25\n")
    pool.write_text(json.dumps({
        "case_id": "zeta_dyn",
        "source": "h5/w1/dyn_zeta.ndjson",
        "shard": "h5/w2/shard_dyn_zeta.toml",
        "modes": ["zz_micro", "int8_strict"],
    }, indent=2))
    return source, shard, pool


def qz_values_from_source(source):
    vals = []
    with source.open() as fh:
        for line in fh:
            if line.strip():
                vals.extend(float(v) for v in json.loads(line).get("vals", []))
    return vals


def expected_stats_from_values(values, mode_id):
    bounds = mode_bounds(mode_id)
    clipped = [clamp(v, bounds["lo"], bounds["hi"]) for v in values]
    return min(clipped), max(clipped)


def expected_scale_from_shard(values, mode_id, layer_id, shard_path):
    stat_min, stat_max = expected_stats_from_values(values, mode_id)
    bounds = dict(mode_bounds(mode_id))
    shard = tomllib.loads(shard_path.read_text())
    layer = shard.get("layers", {}).get(layer_id, {})
    if "lo" in layer:
        bounds["lo"] = layer["lo"]
    if "hi" in layer:
        bounds["hi"] = layer["hi"]
    mid = (stat_min + stat_max) / 2.0
    clipped = [round(clamp(v, bounds["lo"], bounds["hi"]), 3) for v in (stat_min, stat_max, mid)]
    base = abs(sum(round(v * 1000) for v in clipped))
    offset = sum(layer_id.encode())
    if mode_id == "int8_strict":
        return (base % 2000) + 256 + offset
    if mode_id == "mixed_edge":
        return (base % 3000) + 512 + (offset * 2)
    if mode_id == "zz_micro":
        return (base % 2500) + 384 + (3 * offset)
    return (base % 1500) + 128 + offset

def test_h0_core():
    """Driver completes and emits rows for every case and mode pair."""
    emit = load_emit()
    assert emit["meta"]["rows_total"] == len(emit["rows"])
    for case_id in CASES:
        for mode_id in MODES:
            got = rows_for(emit, case_id, mode_id)
            assert got, f"missing rows for {case_id}/{mode_id}"


def test_j4_row():
    """Each row_digest matches sha256 of canonical row bytes."""
    emit = load_emit()
    for row in emit["rows"]:
        expected = ruby_row_digest(
            row["case_id"],
            row["mode_id"],
            row["layer_id"],
            row["scale_u32"],
            row["stat_min"],
            row["stat_max"],
            row["replay_tag"],
        )
        assert row["row_digest"] == expected




def test_b2_clip_order_scale():
    """Known layer scales reflect clip-before-round and layer-bound overrides."""
    emit = load_emit()
    targets = [("sage", "int8_strict", "L0"), ("rowan", "mixed_edge", "L1")]
    by_key = {(r["case_id"], r["mode_id"], r["layer_id"]): r for r in emit["rows"]}
    for case_id, mode_id, layer_id in targets:
        row = by_key[(case_id, mode_id, layer_id)]
        assert row["scale_u32"] == expected_scale(case_id, mode_id, layer_id)

def test_n2_prof():
    """stat_min/stat_max are computed from per-mode clipped tensor values."""
    emit = load_emit()
    for case_id in CASES:
        for mode_id in MODES:
            exp_min, exp_max = expected_stats(case_id, mode_id)
            mode_rows = rows_for(emit, case_id, mode_id)
            assert mode_rows
            for row in mode_rows:
                assert abs(row["stat_min"] - exp_min) < 1e-9
                assert abs(row["stat_max"] - exp_max) < 1e-9
        fp_pair = expected_stats(case_id, "fp16_baseline")
        strict_pair = expected_stats(case_id, "int8_strict")
        assert fp_pair != strict_pair, f"mode clipping should differ for {case_id}"


def test_k8_base():
    """fp16_baseline rows remain present after mixed_edge oriented fixes."""
    emit = load_emit()
    for case_id in CASES:
        rows = rows_for(emit, case_id, "fp16_baseline")
        assert len(rows) >= 2
        assert all(r["scale_u32"] > 0 for r in rows)


def test_v3_dual():
    """Live accumulation differs from poisoned replay bytes until recovery runs."""
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run(POISON, cwd=ROOT, check=True)
    poisoned = load_emit()
    assert any(r["replay_tag"] == "replay" for r in poisoned["rows"])
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run(RECOVERY, cwd=ROOT, check=True)
    live = load_emit()
    assert all(r["replay_tag"] == "live" for r in live["rows"])


def test_r5_phase():
    """Repeat cleanup without recovery leaves replay-tagged rows."""
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run(POISON, cwd=ROOT, check=True)
    emit = load_emit()
    assert any(r["replay_tag"] == "replay" for r in emit["rows"])


def test_m1_trap():
    """Stage snapshot tallies alone do not satisfy terminal emit grading."""
    stub = json.loads((ENV_ROOT / "fixtures/stage_snaps/q2_stub.json").read_text())
    assert stub["headline"]
    emit = load_emit()
    assert emit["meta"]["rows_total"] > sum(stub["headline"].values())


def test_z3_qz():
    """Held-out QZ fixtures produce valid digests with per-layer scale spread."""
    emit = load_emit()
    rowan_edge = [r for r in emit["rows"] if r["case_id"] == "rowan" and r["mode_id"] == "mixed_edge"]
    scales = {r["layer_id"]: r["scale_u32"] for r in rowan_edge}
    assert len(scales) >= 2
    assert len(set(scales.values())) >= 2
    for row in rowan_edge:
        expected = ruby_row_digest(
            row["case_id"],
            row["mode_id"],
            row["layer_id"],
            row["scale_u32"],
            row["stat_min"],
            row["stat_max"],
            row["replay_tag"],
        )
        assert row["row_digest"] == expected


def test_q4_dynamic_qz_pool_source_shard_and_modes():
    """Verifier-created QZ files drive source/shard resolution and dynamic modes."""
    source, shard, _pool = write_dynamic_qz_case()
    emit = load_emit()
    zeta_rows = [r for r in emit["rows"] if r["case_id"] == "zeta_dyn"]
    assert zeta_rows, "dynamic QZ case was not emitted"
    assert {r["mode_id"] for r in zeta_rows} == {"zz_micro", "int8_strict"}
    assert {r["layer_id"] for r in zeta_rows} == {"A2", "Z9"}
    values = qz_values_from_source(source)
    by_key = {(r["mode_id"], r["layer_id"]): r for r in zeta_rows}
    for mode_id in ("zz_micro", "int8_strict"):
        exp_min, exp_max = expected_stats_from_values(values, mode_id)
        for layer_id in ("A2", "Z9"):
            row = by_key[(mode_id, layer_id)]
            assert abs(row["stat_min"] - exp_min) < 1e-9
            assert abs(row["stat_max"] - exp_max) < 1e-9
            assert row["scale_u32"] == expected_scale_from_shard(values, mode_id, layer_id, shard)
            assert row["row_digest"] == ruby_row_digest(
                "zeta_dyn", mode_id, layer_id, row["scale_u32"],
                row["stat_min"], row["stat_max"], row["replay_tag"]
            )
