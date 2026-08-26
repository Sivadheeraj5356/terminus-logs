"""Verifier for ghost densify SRI seal emission under pol_contract formulas."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "ghost_seal.json"
WORK = APP / "work"
ANNEX = APP / "data" / "annex_slice36"
PROFILES = APP / "data" / "bands" / "profiles"
FIXTURE = APP / "fixtures" / "closed_algebra.json"
CORE_TOOLS = ("sep_tool", "fold_tool", "tie_tool")
T0 = 1.0e-9


def sha16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def fmt6(x: float) -> str:
    return f"{x:.6f}"


def fmt12(x: float) -> str:
    return f"{x:.12f}"


def load_manifest_paths() -> list[Path]:
    lines = (ANNEX / "manifest.tsv").read_text().splitlines()[1:]
    paths = []
    for line in lines:
        if not line.strip():
            continue
        _, rel = line.split("\t", 1)
        paths.append(ANNEX / rel)
    return paths


def expected_cut_rows() -> list[dict]:
    rows: list[dict] = []
    for path in load_manifest_paths():
        inst = json.loads(path.read_text())
        frames = sorted(inst["frames"], key=lambda f: f["lane_id"])
        for fr in frames:
            span = sha16(
                f"{fr['lane_id']}|{inst['client_pin']}|{fr['pin_hex']}|{fmt6(float(fr['tick_cost']))}"
            )
            rows.append(
                {
                    "instance_id": inst["id"],
                    "lane_id": fr["lane_id"],
                    "span_hex": span,
                    "tick_cost": float(fr["tick_cost"]),
                    "density_hint": float(fr["density_hint"]),
                }
            )
    rows.sort(key=lambda r: (r["instance_id"], r["lane_id"]))
    return rows


def min_densify_floor() -> float:
    floors = []
    for ppath in sorted(PROFILES.glob("*.json")):
        floors.append(float(json.loads(ppath.read_text())["densify_floor"]))
    return min(floors)


def expected_pack(cut_rows: list[dict]) -> dict:
    floor = min_densify_floor()
    rows = []
    for r in cut_rows:
        lane_hex = sha16(
            f"{r['instance_id']}|{r['lane_id']}|{fmt6(r['density_hint'])}|{r['span_hex']}"
        )
        rows.append(
            {
                "instance_id": r["instance_id"],
                "lane_id": r["lane_id"],
                "lane_hex": lane_hex,
                "floor_ratio": r["density_hint"] / floor,
            }
        )
    rows.sort(key=lambda x: (x["instance_id"], x["lane_id"]))
    joined = "|".join(r["lane_hex"] for r in rows)
    echo = sha16(joined)
    return {
        "packed_context_hex": echo,
        "echo_hex": echo,
        "pack_rows": rows,
    }


def expected_bands(packed: str, pack_rows: list[dict]) -> tuple[list[dict], float]:
    lanes = sorted({r["lane_id"] for r in pack_rows})
    kid = ",".join(lanes)
    band_rows = []
    imb_max = 0.0
    for ppath in sorted(PROFILES.glob("*.json")):
        prof = json.loads(ppath.read_text())
        sum_e = 0.0
        sum_E = 0.0
        for band in prof["bands"]:
            E = float(band["E"])
            sum_E += E
            e_admit = E
            sum_e += e_admit
            band_rows.append(
                {
                    "profile_id": prof["id"],
                    "band_xfer_hex": sha16(
                        f"{prof['id']}:{band['name']}:{fmt12(e_admit)}:{packed}"
                    ),
                    "kernel_span_hex": sha16(
                        f"{prof['id']}:{band['name']}:{kid}:{packed}"
                    ),
                    "e_admit": e_admit,
                }
            )
        imb_max = max(imb_max, abs(sum_e - sum_E))
    return band_rows, imb_max


def expected_map() -> dict:
    cut = expected_cut_rows()
    pack = expected_pack(cut)
    bands, imb = expected_bands(pack["packed_context_hex"], pack["pack_rows"])
    annex_concat = "".join(p.read_text() for p in load_manifest_paths())
    xfer_join = "|".join(b["band_xfer_hex"] for b in bands)
    replay = sha16(annex_concat + ":" + pack["packed_context_hex"] + ":" + xfer_join)
    reweights = json.loads(FIXTURE.read_text())["strategy_scan_reweights"]
    strategy_hold = 0
    violations = 0
    if imb > T0:
        violations += 1
    for row in pack["pack_rows"]:
        if row["floor_ratio"] + T0 < 1.0:
            violations += 1
    for w in reweights:
        ok = all(row["floor_ratio"] / w + T0 >= 1.0 for row in pack["pack_rows"])
        if ok:
            strategy_hold += 1
        else:
            violations += 1
    local_ok = imb <= T0 and all(r["floor_ratio"] + T0 >= 1.0 for r in pack["pack_rows"])
    return {
        "schema_version": "1.0",
        "band_rows": bands,
        "pack_rows": pack["pack_rows"],
        "echo_hex": pack["echo_hex"],
        "replay_root": replay,
        "algebra_violations": violations,
        "local_witness_ok": local_ok,
        "strategy_scan_hold": strategy_hold,
        "packed_context_hex": pack["packed_context_hex"],
    }


def _assert_java_tools() -> None:
    classes = WORK / "classes"
    assert classes.is_dir()
    for name in ("q7/SepH.class", "m4/FoldG.class", "v9/TieW.class"):
        path = classes / name
        assert path.exists(), name
        assert path.stat().st_size > 0
    for name, entry in (
        ("sep_tool", "q7.SepMain"),
        ("fold_tool", "m4.FoldMain"),
        ("tie_tool", "v9.TieMain"),
    ):
        tool = WORK / name
        assert tool.exists()
        body = tool.read_text(encoding="utf-8", errors="replace")
        assert "java" in body.lower()
        assert entry in body


def compile_java_cores() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for name in CORE_TOOLS:
        path = WORK / name
        if path.exists():
            path.unlink()
    for side in ("cut.json", "pack.json"):
        path = WORK / side
        if path.exists():
            path.unlink()
    classes = WORK / "classes"
    if classes.exists():
        for p in classes.rglob("*.class"):
            p.unlink()
    subprocess.run(
        ["bash", "/app/environment/driver/compile_cores.sh"],
        check=True,
        cwd="/app",
    )
    _assert_java_tools()


def run_native_pipeline() -> dict:
    compile_java_cores()
    subprocess.run(
        [
            "/app/work/sep_tool",
            "/app/data/annex_slice36",
            "/app/data/bands/profiles",
            "/app/work/cut.json",
        ],
        check=True,
        cwd="/app",
    )
    env = dict(os.environ)
    env["CUT_CTX"] = "/app/work/cut.json"
    subprocess.run(
        [
            "/app/work/fold_tool",
            "/app/data/annex_slice36",
            "/app/data/bands/profiles",
            "/app/work/pack.json",
        ],
        check=True,
        cwd="/app",
        env=env,
    )
    subprocess.run(
        [
            "/app/work/tie_tool",
            "/app/data/annex_slice36",
            "/app/work",
            "/app/output/ghost_seal.json",
        ],
        check=True,
        cwd="/app",
    )
    _assert_java_tools()
    assert (WORK / "cut.json").exists()
    assert (WORK / "pack.json").exists()
    return json.loads(OUT.read_text())


@pytest.fixture(scope="module")
def expected():
    return expected_map()


@pytest.fixture(scope="module")
def actual(expected):  # noqa: ARG001
    return run_native_pipeline()


def test_q7_span_lock(actual, expected):
    """band_xfer_hex matches digests under packed context from cut+densify."""
    got = {(r["profile_id"], r["band_xfer_hex"]) for r in actual["band_rows"]}
    want = {(r["profile_id"], r["band_xfer_hex"]) for r in expected["band_rows"]}
    assert got == want
    assert len(actual["band_rows"]) == len(expected["band_rows"])
    got_e = sorted((r["band_xfer_hex"], float(r["e_admit"])) for r in actual["band_rows"])
    want_e = sorted((r["band_xfer_hex"], float(r["e_admit"])) for r in expected["band_rows"])
    assert got_e == want_e


def test_q7_kernel_hex(actual, expected):
    """kernel_span_hex identity across densify lane sets."""
    got = {(r["profile_id"], r["kernel_span_hex"]) for r in actual["band_rows"]}
    want = {(r["profile_id"], r["kernel_span_hex"]) for r in expected["band_rows"]}
    assert got == want


def test_m4_mux_hold(actual, expected):
    """densify floor_ratio holds under T0."""
    assert len(actual["pack_rows"]) == len(expected["pack_rows"])
    for row in actual["pack_rows"]:
        assert row["floor_ratio"] + T0 >= 1.0
    got = {(r["instance_id"], r["lane_id"], r["lane_hex"]) for r in actual["pack_rows"]}
    want = {(r["instance_id"], r["lane_id"], r["lane_hex"]) for r in expected["pack_rows"]}
    assert got == want


def test_m4_pair_echo(actual, expected):
    """echo_hex matches densify lane concatenation."""
    assert actual["echo_hex"] == expected["echo_hex"]
    assert len(actual["echo_hex"]) == len(expected["echo_hex"])


def test_v9_zero_hit(actual, expected):
    """independent replay closes obligation 486 under strategy scan."""
    assert actual["schema_version"] == expected["schema_version"]
    assert actual["replay_root"] == expected["replay_root"]
    assert actual["algebra_violations"] == expected["algebra_violations"]
    assert actual["strategy_scan_hold"] == expected["strategy_scan_hold"]
    assert actual["strategy_scan_hold"] == len(
        json.loads(FIXTURE.read_text())["strategy_scan_reweights"]
    )
    assert "local_witness_ok" in actual
    assert isinstance(actual["local_witness_ok"], bool)
    assert actual["local_witness_ok"] == expected["local_witness_ok"]


def test_v9_overwrite_trap(actual, expected):
    """deleting output and recompiling/rerunning tools regenerates authoritative report."""
    OUT.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "band_rows": [],
                "pack_rows": [],
                "echo_hex": "dead",
                "replay_root": "beef",
                "algebra_violations": 99,
                "local_witness_ok": True,
                "strategy_scan_hold": 0,
            }
        )
    )
    again = run_native_pipeline()
    assert again["replay_root"] == expected["replay_root"]
    assert again["algebra_violations"] == expected["algebra_violations"]
    assert again["echo_hex"] == expected["echo_hex"]
    assert again["band_rows"]
    assert again["pack_rows"]
    assert again["local_witness_ok"] == expected["local_witness_ok"]
    _assert_java_tools()
