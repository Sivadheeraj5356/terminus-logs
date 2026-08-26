"""Behavioral verifier for the hypersonic fragment cascade epoch atlas.

Rebuilds binaries via test.sh, drives cascade-ingest / cascade-export through
subprocess, and compares every artifact to an independent Python reference that
reimplements RK2 Kepler propagation, flare drag, sphere collision, and
momentum/energy-conserving fragment spawn. Hidden catalogs under
/opt/verifier-fixtures exercise flare density replacement and multi-body chain
collisions separately from the bundled LEO catalogs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

APP = Path("/app")
BIN = APP / "bin"
INGEST = BIN / "cascade-ingest"
EXPORT = BIN / "cascade-export"
STATE = APP / "state"
OUTPUT = APP / "output"
BUNDLED_ALPHA = APP / "catalogs" / "leo-alpha"
BUNDLED_BRAVO = APP / "catalogs" / "leo-bravo"
HIDDEN = Path("/opt/verifier-fixtures")

MU_EARTH = 3.986004418e14
R_EARTH = 6_371_000.0
RHO0 = 1.225
SCALE_H = 8500.0
DEFAULT_CD = 2.2
TOL = 1e-4


def round6(v: float) -> float:
    return round(v * 1_000_000) / 1_000_000


def mag(v: dict) -> float:
    return math.sqrt(v["x"] ** 2 + v["y"] ** 2 + v["z"] ** 2)


def add(a: dict, b: dict) -> dict:
    return {"x": a["x"] + b["x"], "y": a["y"] + b["y"], "z": a["z"] + b["z"]}


def sub(a: dict, b: dict) -> dict:
    return {"x": a["x"] - b["x"], "y": a["y"] - b["y"], "z": a["z"] - b["z"]}


def scale(v: dict, s: float) -> dict:
    return {"x": v["x"] * s, "y": v["y"] * s, "z": v["z"] * s}


def unit(v: dict) -> dict:
    m = mag(v)
    if m < 1e-15:
        return {"x": 1.0, "y": 0.0, "z": 0.0}
    return scale(v, 1.0 / m)


def cross(a: dict, b: dict) -> dict:
    return {
        "x": a["y"] * b["z"] - a["z"] * b["y"],
        "y": a["z"] * b["x"] - a["x"] * b["z"],
        "z": a["x"] * b["y"] - a["y"] * b["x"],
    }


def ortho_basis(n: dict) -> tuple[dict, dict]:
    ref = {"x": 1.0, "y": 0.0, "z": 0.0} if abs(n["x"]) < 0.9 else {"x": 0.0, "y": 1.0, "z": 0.0}
    u = unit(cross(n, ref))
    w = cross(n, u)
    return u, w


def _json_number(n: float | int) -> str:
    """Match ECMAScript JSON.stringify for finite numbers."""
    if isinstance(n, bool):
        return "true" if n else "false"
    if isinstance(n, int) and not isinstance(n, bool):
        return str(n)
    f = float(n)
    if f == 0:
        return "0"
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return json.dumps(f)


def canonical_stringify(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _json_number(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ",".join(canonical_stringify(x) for x in v) + "]"
    keys = sorted(v.keys())
    parts = [f"{json.dumps(k)}:{canonical_stringify(v[k])}" for k in keys]
    return "{" + ",".join(parts) + "}"


def payload_hash(obj) -> str:
    return hashlib.sha256(canonical_stringify(obj).encode()).hexdigest()


def load_catalog(catalog_dir: Path):
    manifest = json.loads((catalog_dir / "manifest.json").read_text())
    bodies = []
    for line in (catalog_dir / "bodies.jsonl").read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        bodies.append(
            {
                "id": obj["id"],
                "mass_kg": obj["mass_kg"],
                "radius_m": obj["radius_m"],
                "pos_m": dict(obj["pos_m"]),
                "vel_mps": dict(obj["vel_mps"]),
                "cd": obj["cd"] if "cd" in obj else DEFAULT_CD,
            }
        )
    flares = []
    for line in (catalog_dir / "flares.jsonl").read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        flares.append(json.loads(line))
    flares.sort(key=lambda f: f["t_sec"])
    bodies_raw = (catalog_dir / "bodies.jsonl").read_bytes()
    flares_raw = (catalog_dir / "flares.jsonl").read_bytes()
    fp = hashlib.sha256(bodies_raw + flares_raw).hexdigest()
    return manifest, bodies, flares, fp


def density_scale(flares, t_sec: float) -> float:
    scale_v = 1.0
    for f in flares:
        if t_sec >= f["t_sec"]:
            scale_v = f["density_scale"]
    return scale_v


def gravity(pos: dict) -> dict:
    r = mag(pos)
    factor = -MU_EARTH / (r**3)
    return scale(pos, factor)


def drag_accel(pos: dict, vel: dict, body: dict, dens: float) -> dict:
    r = mag(pos)
    alt = r - R_EARTH
    if alt < 0:
        return {"x": 0.0, "y": 0.0, "z": 0.0}
    rho = RHO0 * math.exp(-alt / SCALE_H) * dens
    area = math.pi * body["radius_m"] ** 2
    speed = mag(vel)
    if speed < 1e-15 or body["mass_kg"] < 1e-15:
        return {"x": 0.0, "y": 0.0, "z": 0.0}
    coeff = -0.5 * rho * body["cd"] * area * speed / body["mass_kg"]
    return scale(vel, coeff)


def accel(pos, vel, body, dens):
    return add(gravity(pos), drag_accel(pos, vel, body, dens))


def propagate_step(body, dt, dens):
    a0 = accel(body["pos_m"], body["vel_mps"], body, dens)
    p_mid = add(body["pos_m"], scale(body["vel_mps"], dt / 2))
    v_mid = add(body["vel_mps"], scale(a0, dt / 2))
    a1 = accel(p_mid, v_mid, body, dens)
    body["pos_m"] = add(body["pos_m"], scale(body["vel_mps"], dt))
    body["vel_mps"] = add(body["vel_mps"], scale(a1, dt))


def detect_collision(bodies):
    best = None
    best_key = None
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            d = mag(sub(bodies[i]["pos_m"], bodies[j]["pos_m"]))
            thr = bodies[i]["radius_m"] + bodies[j]["radius_m"]
            if d < thr:
                id_a, id_b = sorted([bodies[i]["id"], bodies[j]["id"]])
                key = (id_a, id_b)
                if best is None or key < best_key:
                    best = (i, j)
                    best_key = key
    return best


def spawn_fragments(a, b, fragment_count, min_sep, t_sec):
    m_tot = a["mass_kg"] + b["mass_kg"]
    mf = m_tot / fragment_count
    rf = (a["radius_m"] ** 3 + b["radius_m"] ** 3) / fragment_count
    rf = rf ** (1.0 / 3.0)
    collision_pt = {
        "x": (a["pos_m"]["x"] * a["mass_kg"] + b["pos_m"]["x"] * b["mass_kg"]) / m_tot,
        "y": (a["pos_m"]["y"] * a["mass_kg"] + b["pos_m"]["y"] * b["mass_kg"]) / m_tot,
        "z": (a["pos_m"]["z"] * a["mass_kg"] + b["pos_m"]["z"] * b["mass_kg"]) / m_tot,
    }
    v_cm = {
        "x": (a["mass_kg"] * a["vel_mps"]["x"] + b["mass_kg"] * b["vel_mps"]["x"]) / m_tot,
        "y": (a["mass_kg"] * a["vel_mps"]["y"] + b["mass_kg"] * b["vel_mps"]["y"]) / m_tot,
        "z": (a["mass_kg"] * a["vel_mps"]["z"] + b["mass_kg"] * b["vel_mps"]["z"]) / m_tot,
    }
    e_total = 0.5 * a["mass_kg"] * mag(a["vel_mps"]) ** 2 + 0.5 * b["mass_kg"] * mag(b["vel_mps"]) ** 2
    e_cm = 0.5 * m_tot * mag(v_cm) ** 2
    e_rel = max(0.0, e_total - e_cm)
    speed = math.sqrt(2 * e_rel / m_tot) if m_tot > 0 else 0.0
    rel_dir = unit(sub(a["vel_mps"], b["vel_mps"]))
    u, w = ortho_basis(rel_dir)
    parents = tuple(sorted([a["id"], b["id"]]))
    fragments = []
    child_ids = []
    for k in range(fragment_count):
        theta = k * 2 * math.pi / fragment_count
        direction = add(scale(u, math.cos(theta)), scale(w, math.sin(theta)))
        vel = add(v_cm, scale(direction, speed))
        pos = add(collision_pt, scale(direction, min_sep))
        child_id = f"{parents[0]}__{parents[1]}__f{k}"
        child_ids.append(child_id)
        fragments.append(
            {
                "id": child_id,
                "mass_kg": mf,
                "radius_m": rf,
                "pos_m": pos,
                "vel_mps": vel,
                "cd": DEFAULT_CD,
            }
        )
    p_total = add(scale(a["vel_mps"], a["mass_kg"]), scale(b["vel_mps"], b["mass_kg"]))
    p_frags = {"x": 0.0, "y": 0.0, "z": 0.0}
    e_frags = 0.0
    for f in fragments:
        p_frags = add(p_frags, scale(f["vel_mps"], f["mass_kg"]))
        e_frags += 0.5 * f["mass_kg"] * mag(f["vel_mps"]) ** 2
    epoch = {
        "t_sec": round6(t_sec),
        "parents": list(parents),
        "child_ids": child_ids,
        "momentum_residual": round6(mag(sub(p_total, p_frags))),
        "energy_residual": round6(abs(e_total - e_frags)),
    }
    return fragments, epoch


def run_reference(catalog_dir: Path, mission_slot: str | None = None):
    manifest, bodies, flares, fp = load_catalog(catalog_dir)
    if mission_slot:
        manifest = dict(manifest)
        manifest["mission_slot"] = mission_slot
    bodies = deepcopy(bodies)
    flares = deepcopy(flares)
    staging = {
        "mission_slot": manifest["mission_slot"],
        "manifest": manifest,
        "bodies": bodies,
        "flares": flares,
        "catalog_fingerprint": fp,
        "staging_hash": "",
    }
    staging["staging_hash"] = payload_hash(staging)

    sim_bodies = deepcopy(bodies)
    epochs = []
    dt = manifest["dt_sec"]
    steps = int(math.ceil(manifest["horizon_sec"] / dt))
    for step in range(steps):
        t = step * dt
        dens = density_scale(flares, t)
        for b in sim_bodies:
            propagate_step(b, dt, dens)
        pair = detect_collision(sim_bodies)
        if pair:
            i, j = pair
            a = sim_bodies[i]
            b = sim_bodies[j]
            frags, epoch = spawn_fragments(
                a, b, manifest["fragment_count"], manifest["min_sep_m"], t
            )
            sim_bodies = [bb for idx, bb in enumerate(sim_bodies) if idx not in (i, j)]
            sim_bodies.extend(frags)
            epochs.append(epoch)

    atlas_bodies = [
        {
            "id": b["id"],
            "final_pos_m": {k: round6(b["pos_m"][k]) for k in ("x", "y", "z")},
            "final_vel_mps": {k: round6(b["vel_mps"][k]) for k in ("x", "y", "z")},
            "mass_kg": round6(b["mass_kg"]),
            "radius_m": round6(b["radius_m"]),
            "survived": True,
        }
        for b in sim_bodies
    ]
    atlas_env = {
        "mission_slot": manifest["mission_slot"],
        "epoch_count": len(epochs),
        "final_body_count": len(atlas_bodies),
        "bodies": atlas_bodies,
    }
    atlas = dict(atlas_env)
    atlas["atlas_hash"] = payload_hash(atlas_env)

    staging_digest = payload_hash(
        {"mission_slot": staging["mission_slot"], "catalog_fingerprint": fp}
    )
    ledger_env = {
        "mission_slot": manifest["mission_slot"],
        "epochs": epochs,
        "total_collisions": len(epochs),
        "staging_digest": staging_digest,
    }
    ledger = dict(ledger_env)
    ledger["ledger_hash"] = payload_hash(ledger_env)
    return staging, atlas, ledger


def reset_runtime():
    if STATE.exists():
        shutil.rmtree(STATE)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    STATE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def run_pipeline(catalog: Path, env_extra: dict | None = None):
    reset_runtime()
    env = os.environ.copy()
    env["CASCADE_CATALOG_DIR"] = str(catalog)
    if env_extra:
        env.update(env_extra)
    r1 = subprocess.run([str(INGEST)], env=env, capture_output=True, text=True)
    assert r1.returncode == 0, r1.stderr + r1.stdout
    r2 = subprocess.run([str(EXPORT)], env=env, capture_output=True, text=True)
    assert r2.returncode == 0, r2.stderr + r2.stdout
    staging = json.loads((STATE / "cascade-staging.json").read_text())
    seal = json.loads((STATE / "ingest-seal.json").read_text())
    atlas = json.loads((OUTPUT / "cascade-fragment-atlas.json").read_text())
    ledger = json.loads((OUTPUT / "collision-epoch-ledger.json").read_text())
    seq = json.loads((STATE / "export-sequence.json").read_text())
    return staging, seal, atlas, ledger, seq


def assert_close_vec(a, b, tol=TOL):
    for k in ("x", "y", "z"):
        assert abs(a[k] - b[k]) <= tol, (k, a[k], b[k])


@pytest.fixture(scope="module", autouse=True)
def _binaries_present():
    assert INGEST.is_file(), "cascade-ingest missing"
    assert EXPORT.is_file(), "cascade-export missing"


def test_ingest_writes_staging_and_seal_alpha():
    """Writes /app/state/cascade-staging.json and /app/state/ingest-seal.json then export artifacts."""
    staging, seal, atlas, ledger, seq = run_pipeline(BUNDLED_ALPHA)
    assert (STATE / "cascade-staging.json").is_file()
    assert (Path("/app/state/cascade-staging.json")).is_file()
    assert (STATE / "ingest-seal.json").is_file()
    assert Path("/app/state/ingest-seal.json").is_file()
    assert Path("/app/output/cascade-fragment-atlas.json").is_file()
    assert Path("/app/output/collision-epoch-ledger.json").is_file()
    assert Path("/app/state/export-sequence.json").is_file()
    assert seal["staging_hash"] == staging["staging_hash"]
    assert seal["catalog_fingerprint"] == staging["catalog_fingerprint"]
    assert atlas["atlas_hash"]
    assert ledger["ledger_hash"]
    assert seq["run_seq"] == 1


def test_bodies_preserve_feed_order_not_id_sort():
    """Bodies in staging must keep bodies.jsonl feed order (not sorted by id)."""
    staging, _, _, _, _ = run_pipeline(BUNDLED_ALPHA)
    ids = [b["id"] for b in staging["bodies"]]
    raw_ids = []
    for line in (BUNDLED_ALPHA / "bodies.jsonl").read_text().splitlines():
        raw_ids.append(json.loads(line)["id"])
    assert ids == raw_ids
    assert ids != sorted(ids) or len(ids) == 1


def test_per_body_cd_honored_from_catalog():
    """Per-body cd from catalog must be preserved in /app/state/cascade-staging.json."""
    staging, _, _, _, _ = run_pipeline(BUNDLED_ALPHA)
    by_id = {b["id"]: b for b in staging["bodies"]}
    assert by_id["DEB-B"]["cd"] == 2.5


def test_catalog_fingerprint_matches_raw_bytes():
    """catalog_fingerprint is sha256 of raw bodies.jsonl then flares.jsonl bytes."""
    staging, seal, _, _, _ = run_pipeline(BUNDLED_ALPHA)
    bodies_raw = (BUNDLED_ALPHA / "bodies.jsonl").read_bytes()
    flares_raw = (BUNDLED_ALPHA / "flares.jsonl").read_bytes()
    expect = hashlib.sha256(bodies_raw + flares_raw).hexdigest()
    assert staging["catalog_fingerprint"] == expect
    assert seal["catalog_fingerprint"] == expect


def test_staging_hash_is_canonical():
    """staging_hash on /app/state/cascade-staging.json uses canonical JSON hashing."""
    staging, _, _, _, _ = run_pipeline(BUNDLED_ALPHA)
    ref, _, _ = run_reference(BUNDLED_ALPHA)
    assert staging["staging_hash"] == ref["staging_hash"]


def test_mission_slot_override():
    """CASCADE_MISSION_SLOT overrides mission_slot across staging, atlas, and ledger."""
    staging, _, atlas, ledger, _ = run_pipeline(
        BUNDLED_ALPHA, {"CASCADE_MISSION_SLOT": "SLOT-OVERRIDE-9"}
    )
    assert staging["mission_slot"] == "SLOT-OVERRIDE-9"
    assert atlas["mission_slot"] == "SLOT-OVERRIDE-9"
    assert ledger["mission_slot"] == "SLOT-OVERRIDE-9"


def test_bravo_catalog_override_dir():
    """CASCADE_CATALOG_DIR absolute override reads leo-bravo and matches reference hashes."""
    staging, _, atlas, ledger, _ = run_pipeline(BUNDLED_BRAVO)
    assert staging["mission_slot"] == "LEO-BRAVO-2"
    assert atlas["mission_slot"] == "LEO-BRAVO-2"
    ref_s, ref_a, ref_l = run_reference(BUNDLED_BRAVO)
    assert atlas["atlas_hash"] == ref_a["atlas_hash"]
    assert ledger["ledger_hash"] == ref_l["ledger_hash"]
    assert staging["staging_hash"] == ref_s["staging_hash"]


def test_export_refuses_missing_staging():
    """cascade-export exits non-zero when /app/state/cascade-staging.json is missing."""
    reset_runtime()
    r = subprocess.run([str(EXPORT)], capture_output=True, text=True)
    assert r.returncode != 0


def test_export_refuses_stale_seal():
    """cascade-export refuses when /app/state/ingest-seal.json staging_hash is stale."""
    run_pipeline(BUNDLED_ALPHA)
    seal = json.loads((STATE / "ingest-seal.json").read_text())
    seal["staging_hash"] = "0" * 64
    (STATE / "ingest-seal.json").write_text(json.dumps(seal))
    r = subprocess.run([str(EXPORT)], capture_output=True, text=True)
    assert r.returncode != 0


def test_alpha_collision_occurs_and_matches_reference():
    """Bundled alpha produces collisions; atlas/ledger match independent reference."""
    staging, _, atlas, ledger, _ = run_pipeline(BUNDLED_ALPHA)
    _, ref_a, ref_l = run_reference(BUNDLED_ALPHA)
    assert atlas["epoch_count"] >= 1
    assert ledger["total_collisions"] == atlas["epoch_count"]
    assert atlas["atlas_hash"] == ref_a["atlas_hash"]
    assert ledger["ledger_hash"] == ref_l["ledger_hash"]
    assert atlas["final_body_count"] == ref_a["final_body_count"]


def test_epoch_residuals_near_zero():
    """Collision epochs conserve momentum and energy within residual tolerance."""
    _, _, _, ledger, _ = run_pipeline(BUNDLED_ALPHA)
    assert ledger["epochs"]
    for ep in ledger["epochs"]:
        assert ep["momentum_residual"] <= 1e-3
        assert ep["energy_residual"] <= 1e-3
        assert ep["parents"][0] < ep["parents"][1]
        assert len(ep["child_ids"]) >= 2


def test_fragment_child_id_format():
    """Child fragment ids follow sorted-parent__f{k} naming from collision-spawn.md."""
    _, _, _, ledger, _ = run_pipeline(BUNDLED_ALPHA)
    ep = ledger["epochs"][0]
    p0, p1 = ep["parents"]
    for i, cid in enumerate(ep["child_ids"]):
        assert cid == f"{p0}__{p1}__f{i}"


def test_atlas_positions_rounded_six_decimals():
    """/app/output/cascade-fragment-atlas.json positions/velocities are rounded to 6 decimals."""
    _, _, atlas, _, _ = run_pipeline(BUNDLED_ALPHA)
    for b in atlas["bodies"]:
        for axis in ("x", "y", "z"):
            assert b["final_pos_m"][axis] == round6(b["final_pos_m"][axis])
            assert b["final_vel_mps"][axis] == round6(b["final_vel_mps"][axis])


def test_staging_digest_binds_mission_and_fingerprint():
    """Ledger staging_digest binds mission_slot and catalog_fingerprint."""
    staging, _, _, ledger, _ = run_pipeline(BUNDLED_ALPHA)
    expect = payload_hash(
        {
            "mission_slot": staging["mission_slot"],
            "catalog_fingerprint": staging["catalog_fingerprint"],
        }
    )
    assert ledger["staging_digest"] == expect


def test_export_sequence_monotonic_and_stable_hash():
    """/app/state/export-sequence.json run_seq increments while atlas_hash stays stable."""
    reset_runtime()
    env = os.environ.copy()
    env["CASCADE_CATALOG_DIR"] = str(BUNDLED_ALPHA)
    assert subprocess.run([str(INGEST)], env=env).returncode == 0
    assert subprocess.run([str(EXPORT)], env=env).returncode == 0
    seq1 = json.loads((STATE / "export-sequence.json").read_text())
    atlas1 = json.loads((OUTPUT / "cascade-fragment-atlas.json").read_text())
    assert subprocess.run([str(EXPORT)], env=env).returncode == 0
    seq2 = json.loads((STATE / "export-sequence.json").read_text())
    atlas2 = json.loads((OUTPUT / "cascade-fragment-atlas.json").read_text())
    assert seq1["run_seq"] == 1
    assert seq2["run_seq"] == 2
    assert atlas1["atlas_hash"] == atlas2["atlas_hash"]
    assert seq1["atlas_hash"] == seq2["atlas_hash"]


def test_flare_absolute_density_scale_not_multiplicative():
    """Hidden flare-trap under /opt/verifier-fixtures: absolute density_scale replacement."""
    cat = Path("/opt/verifier-fixtures") / "flare-trap"
    if not cat.is_dir():
        pytest.skip("hidden flare-trap missing")
    _, _, atlas, ledger, _ = run_pipeline(cat)
    _, ref_a, ref_l = run_reference(cat)
    assert atlas["atlas_hash"] == ref_a["atlas_hash"]
    assert ledger["total_collisions"] == ref_l["total_collisions"]
    assert len(ledger["epochs"]) == len(ref_l["epochs"])
    for got, exp in zip(ledger["epochs"], ref_l["epochs"]):
        assert got["parents"] == exp["parents"]
        assert got["child_ids"] == exp["child_ids"]
        assert got["t_sec"] == exp["t_sec"]
    flares = []
    for line in (cat / "flares.jsonl").read_text().splitlines():
        flares.append(json.loads(line))
    assert density_scale(flares, 40.0) == 12.0
    product = 1.0
    for f in flares:
        product *= f["density_scale"]
    assert product != 12.0
    assert atlas["atlas_hash"] == ref_a["atlas_hash"]


def test_hidden_chain_reaction_independent_of_bundled():
    """Hidden chain-reaction under /opt/verifier-fixtures is independent of bundled alpha."""
    cat = Path("/opt/verifier-fixtures") / "chain-reaction"
    if not cat.is_dir():
        pytest.skip("hidden chain-reaction missing")
    _, _, atlas, ledger, _ = run_pipeline(cat)
    _, ref_a, ref_l = run_reference(cat)
    assert atlas["atlas_hash"] == ref_a["atlas_hash"]
    assert ledger["ledger_hash"] == ref_l["ledger_hash"]
    assert atlas["epoch_count"] >= 1
    # Bundled alpha hash must not equal chain hash (independent fixture)
    _, _, atlas_b, _, _ = run_pipeline(BUNDLED_ALPHA)
    assert atlas["atlas_hash"] != atlas_b["atlas_hash"]


def test_decoy_not_on_export_hot_path():
    """Export hot path must not import /app/src/decoy/wrap.ts."""
    export_src = (APP / "src" / "bin" / "export.ts").read_text()
    assert "decoy" not in export_src
    assert "wrap" not in export_src or "decoy/wrap" not in export_src


def test_flares_sorted_by_t_sec_in_staging():
    """Flares in staging are sorted by t_sec ascending."""
    staging, _, _, _, _ = run_pipeline(BUNDLED_BRAVO)
    times = [f["t_sec"] for f in staging["flares"]]
    assert times == sorted(times)


def test_ledger_epochs_match_reference_timestamps():
    """/app/output/collision-epoch-ledger.json epochs match reference timestamps and parents."""
    _, _, _, ledger, _ = run_pipeline(BUNDLED_ALPHA)
    _, _, ref_l = run_reference(BUNDLED_ALPHA)
    assert len(ledger["epochs"]) == len(ref_l["epochs"])
    for got, exp in zip(ledger["epochs"], ref_l["epochs"]):
        assert got["t_sec"] == exp["t_sec"]
        assert got["parents"] == exp["parents"]
        assert got["child_ids"] == exp["child_ids"]
