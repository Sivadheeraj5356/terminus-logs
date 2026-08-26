"""Verifier for the physics contact resolution debugger task."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

SCHEMA = Path("/app/spec/OUTPUT_SCHEMA.md")
INPUT_FMT = Path("/app/spec/INPUT_FORMAT.md")
REPORT = Path("/app/results/contact_stability_report.json")
_ART_BASE = Path(os.environ.get("PHYSICS_VERIFIER_ARTIFACT_DIR", "/tmp/physics-verifier-artifacts"))
REPORT_FIRST = _ART_BASE / "report_first.json"
REPORT_SECOND = _ART_BASE / "report_second.json"
REPORT_SWAP = _ART_BASE / "report_swap.json"
REPORT_SWAP_SECOND = _ART_BASE / "report_swap_second.json"
REPORT_PROBE7 = _ART_BASE / "report_probe7.json"
REPORT_SYMLINK = _ART_BASE / "report_symlink.json"
REPORT_TOLERANCE = _ART_BASE / "report_tolerance.json"
REPORT_BP_REVERSED = _ART_BASE / "report_bp_reversed.json"
REPORT_DEDUP = _ART_BASE / "report_dedup.json"
REPORT_TRUNC = _ART_BASE / "report_trunc.json"
REPORT_OVER_TOL = _ART_BASE / "report_over_tol.json"
REPORT_BOUNDARY = _ART_BASE / "report_boundary.json"
REPORT_RESTSEP = _ART_BASE / "report_restsep.json"
REPORT_EMPTY06 = _ART_BASE / "report_empty06.json"
REPORT_REORDER05 = _ART_BASE / "report_reorder05.json"
REPORT_FMTVER = _ART_BASE / "report_fmtver.json"
REPORT_NESTED = _ART_BASE / "report_nested.json"
REPORT_FULL10 = _ART_BASE / "report_full10.json"
REPORT_REV03 = _ART_BASE / "report_rev03.json"
REPORT_SEMI = _ART_BASE / "report_semi.json"
REPORT_DUPCID = _ART_BASE / "report_dupcid.json"
REPORT_CAPTURE = _ART_BASE / "report_capture.json"
REPORT_EMPTSTRESS = _ART_BASE / "report_emptstress.json"
REPORT_MULTI13 = _ART_BASE / "report_multi13.json"
REPORT_TUNSUB = _ART_BASE / "report_tunsub.json"
REPORT_BTICK = _ART_BASE / "report_btick.json"
REPORT_DUPFRAME = _ART_BASE / "report_dupframe.json"
REPORT_HORZN = _ART_BASE / "report_horzn.json"
REPORT_RESTONCE = _ART_BASE / "report_restonce.json"
REPORT_SLEEPOVER = _ART_BASE / "report_sleepover.json"
REPORT_SLEEPUNDER = _ART_BASE / "report_sleepunder.json"
REPORT_ABSPATH = _ART_BASE / "report_abspath.json"
REPORT_APPROACH = _ART_BASE / "report_approach.json"
REPORT_SWAPBODY = _ART_BASE / "report_swapbody.json"
REPORT_MISSSTRESS = _ART_BASE / "report_missstress.json"
REPORT_METAREST = _ART_BASE / "report_metarest.json"
REPORT_PERMDECOY = _ART_BASE / "report_permdecoy.json"
BIN = Path("/app/bin/contact-resolver")
MAIN_GO = Path("/app/replay/main.go")
PIPELINE_GO = Path("/app/engine/orchestrator/pipeline.go")
SOLVER_GO = Path("/app/engine/solver/resolver.go")
POLICY = Path("/app/rules/contact_policy.yaml")
SCENARIO_DIR = Path("/app/scenarios")
STUB_NOT_IMPLEMENTED = "solver.AnalyzeScene not implemented"

BUNDLED_DATA_CHECKSUMS: dict[str, str] = {
    "scene_01.json": "19efebddb609e8f1910f74d0b85e385455e4b60b85d2d9ad6cdcd8c2c4ce3ba5",
    "scene_02.json": "b29d7d323f55ff7a298d2f56ddcbe9ef5e94e9c835762c2bda9bcd17147b447a",
    "scene_03.json": "e7c2ff7d30aeba18d2211b2fa675a825325a6b9765aed8720855704d7116f40e",
    "scene_04.json": "87e95e5f4756fe8e7ddac39c5fbdebd13d46aefaafce4a78a9d8dad9a7c8f065",
    "scene_05.json": "b12b4d9589e6a6e794deca8889d50609b5665e4e5a51bd535ed594252b316eed",
    "scene_06.json": "67dde75cdfa65653af6a7fcef426fc531659d32be0a8eaab5cd5a60bc9dc2781",
    "scene_07.json": "030e08ec00fa0bdc45b872426d6215f6b78d249bb27f4f8d38d3cf55f57b7107",
    "scene_08.json": "6bc3fdfd6a359dc1bddecc45ab9b8c1cd5f604120c6d57b6c3fd256ce690d7d8",
    "scene_09.json": "dd4d0f92155478f224a297eb9137721616f5674d6380469d2bfd913b62cac568",
    "scene_10.json": "431ced725ab6b35f21ffb4f6ad5fc56ced1dd8251770aab2bf40ce193955c431",
    "scene_11.json": "4e6ca419656d38d71107751c042315799b498df0b304e31de2c7f1fb7cced1d2",
    "scene_12.json": "013028801f4009ec54a5a7966deddafb72d5b6b2e772f5e8da13eb1e47eb463c",
    "scene_13.json": "b8dd9da0c8c2451c05764de1a41709ddddc60a50a96433b39f3cfdb8896f0b52",
    "scene_14.json": "5923f08616f761432314b51df0a6042f2f80947e2c0931c124d63ba86737363a",
    "scene_15.json": "8a5295fe33e4a7628bd7e09734eab155c7fed9ff9ec6faeb93914883be3af77c",
    "scene_16.json": "f1175f614c70687f996c6c588dca61fcb46c5b0c7eaada85fc0066688932b9af",
    "scene_17.json": "7a3fa7be78b418c54336315732915bc612c4174ea654c52e9531dd9f71e99f39",
    "scene_18.json": "3d405ebc3e246b5c048718d078f333302d8fad09ba3aaf46c396e7c3abfb5304",
    "scene_19.json": "5423a151836429a0f97ef78c119dff85698efb67cde085b1690f5ad87dd8f614",
    "scene_20.json": "b6f09cc7ca35d20f98af0ebaace19853ba7bd8e9554d57085818922c114cb049",
}

EXPECTED_MAIN_GO_SHA256 = "62ab7670007d76d55ef4e8c2ebd3eaacc5fa511d0260a2ba2b654a5e808dedbb"
EXPECTED_SCHEMA_SHA256 = "76e49864283287f5abf166a962dc76550a119392bf8337ff7702d22d5df85ff1"
EXPECTED_INPUT_FMT_SHA256 = "feb2fc6598c8e4e20aca0c87b407fddf16f178ea6a5703fe1fa3f5b72d537b00"
EXPECTED_POLICY_SHA256 = "99aeba09ca3cc39c70f4a0de82365e1b2b3ccbde76a8356da669ff6b4015cae2"

SUMMARY_KEYS = [
    "scenes_analyzed",
    "unstable_scenes",
    "stable_scenes",
    "total_violations",
    "stress_replays_run",
    "stress_replays_passed",
]

SCENE_KEYS = [
    "scene_id",
    "unstable",
    "violations",
    "max_penetration_m",
    "impulse_chain_len",
    "stress",
]

STRESS_KEYS = ["replays_run", "replays_passed", "validated"]
VIOLATION_KEYS = ["kind", "frame", "bodies", "detail"]

EXPECTED_SCENE_IDS = [f"scene_{i:02d}" for i in range(1, 21)]

EXPECTED_VIOLATION_KINDS: dict[str, set[str]] = {
    "scene_01": {"penetration_artifact"},
    "scene_02": set(),
    "scene_03": {"stacking_instability"},
    "scene_04": set(),
    "scene_05": {"impulse_chain_break"},
    "scene_06": set(),
    "scene_07": {"friction_drift"},
    "scene_08": set(),
    "scene_09": {"restitution_violation"},
    "scene_10": {"stale_manifold"},
    "scene_11": {"penetration_artifact", "phase_mismatch"},
    "scene_12": set(),
    "scene_13": {"layer_filter_miss"},
    "scene_14": {"constraint_violation"},
    "scene_15": set(),
    "scene_16": {"phase_mismatch"},
    "scene_17": set(),
    "scene_18": {"tunneling"},
    "scene_19": {"sleep_activation_error"},
    "scene_20": set(),
}

EXPECTED_IMPULSE_CHAIN_LEN: dict[str, int] = {f"scene_{i:02d}": 1 for i in range(1, 21)}
EXPECTED_IMPULSE_CHAIN_LEN["scene_05"] = 2

EXPECTED_VIOLATION_RECORDS: dict[str, list[dict[str, object]]] = {
    "scene_01": [
        {"kind": "penetration_artifact", "frame": 0, "bodies": ["A", "B"], "detail": "penetration 0.0025 m"},
    ],
    "scene_03": [
        {"kind": "stacking_instability", "frame": 2, "bodies": ["A", "B"], "detail": "monotonic penetration growth"},
    ],
    "scene_05": [
        {"kind": "impulse_chain_break", "frame": 0, "bodies": ["A", "C"], "detail": "impulse transfer below chain minimum"},
    ],
    "scene_07": [
        {"kind": "friction_drift", "frame": 0, "bodies": ["A", "B"], "detail": "tangent impulse exceeds drift threshold"},
    ],
    "scene_09": [
        {"kind": "restitution_violation", "frame": 0, "bodies": ["A", "B"], "detail": "restitution out of clamp"},
    ],
    "scene_10": [
        {"kind": "stale_manifold", "frame": 3, "bodies": ["m10"], "detail": "manifold survived after contact removal"},
    ],
    "scene_11": [
        {"kind": "penetration_artifact", "frame": 0, "bodies": ["A", "B"], "detail": "penetration 0.0020 m"},
        {"kind": "phase_mismatch", "frame": 0, "bodies": ["A", "C"], "detail": "narrowphase pair missing from broadphase"},
    ],
    "scene_13": [
        {"kind": "layer_filter_miss", "frame": 0, "bodies": ["A", "B"], "detail": "layer masks do not intersect"},
    ],
    "scene_14": [
        {"kind": "constraint_violation", "frame": 0, "bodies": ["A", "B"], "detail": "separation exceeds limit"},
    ],
    "scene_16": [
        {"kind": "phase_mismatch", "frame": 0, "bodies": ["A", "B"], "detail": "narrowphase pair missing from broadphase"},
    ],
    "scene_18": [
        {"kind": "tunneling", "frame": 1, "bodies": ["A"], "detail": "displacement exceeds velocity threshold"},
    ],
    "scene_19": [
        {"kind": "sleep_activation_error", "frame": 0, "bodies": ["A"], "detail": "sleeping body moving too fast"},
    ],
}

EXPECTED_STRESS_VALIDATED: dict[str, bool] = {f"scene_{i:02d}": True for i in range(1, 21)}
EXPECTED_STRESS_VALIDATED["scene_14"] = False

EXPECTED_MAX_PENETRATION: dict[str, float] = {
    "scene_01": 0.0025,
    "scene_02": 0.0005,
    "scene_03": 0.0009,
    "scene_04": 0.0004,
    "scene_05": 0.0005,
    "scene_06": 0.0005,
    "scene_07": 0.0005,
    "scene_08": 0.0005,
    "scene_09": 0.0005,
    "scene_10": 0.0005,
    "scene_11": 0.002,
    "scene_12": 0.0005,
    "scene_13": 0.0005,
    "scene_14": 0.0005,
    "scene_15": 0.0005,
    "scene_16": 0.0005,
    "scene_17": 0.0005,
    "scene_18": 0.0005,
    "scene_19": 0.0005,
    "scene_20": 0.0005,
}

EXPECTED_STRESS_TALLIES: dict[str, dict[str, int | bool]] = {
    "scene_10": {"replays_run": 1, "replays_passed": 1, "validated": True},
    "scene_13": {"replays_run": 1, "replays_passed": 1, "validated": True},
    "scene_14": {"replays_run": 1, "replays_passed": 1, "validated": False},
}

EXPECTED_UNSTABLE: dict[str, bool] = {
    "scene_01": True,
    "scene_02": False,
    "scene_03": True,
    "scene_04": False,
    "scene_05": True,
    "scene_06": False,
    "scene_07": True,
    "scene_08": False,
    "scene_09": True,
    "scene_10": True,
    "scene_11": True,
    "scene_12": False,
    "scene_13": True,
    "scene_14": True,
    "scene_15": False,
    "scene_16": True,
    "scene_17": False,
    "scene_18": True,
    "scene_19": True,
    "scene_20": False,
}

_ARTIFACTS_READY = False


def prepare_verifier_artifacts() -> None:
    """Build resolver and capture default and swap reports before pytest."""
    global _ARTIFACTS_READY
    if _ARTIFACTS_READY:
        return
    _ART_BASE.mkdir(parents=True, exist_ok=True)

    subprocess.run(["make", "build"], cwd="/app", check=False, timeout=180)

    def _run(env: dict[str, str] | None = None) -> bool:
        if not BIN.exists():
            return False
        env_map = {**os.environ, **(env or {})}
        result = subprocess.run(
            [str(BIN)],
            cwd="/app",
            env=env_map,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        return result.returncode == 0

    def _copy(dest: Path) -> None:
        if REPORT.exists():
            shutil.copy2(REPORT, dest)

    if _run():
        _copy(REPORT_FIRST)
    if _run():
        _copy(REPORT_SECOND)

    swap_root = Path("/tmp/physics-verify-data")
    if swap_root.exists():
        shutil.rmtree(swap_root)
    swap_root.mkdir(parents=True)
    shutil.copytree(SCENARIO_DIR, swap_root, dirs_exist_ok=True)
    src = SCENARIO_DIR / "scene_02.json"
    dst = swap_root / "scene_01.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    data["scene_id"] = "scene_01"
    dst.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    decoy = {
        "scene_id": "scene_99",
        "bodies": {"X": {"layer": 1, "mass": 1.0, "sleeping": False}},
        "layers": {"1": 1},
        "frames": [],
    }
    (swap_root / "scene_99.json").write_text(
        json.dumps(decoy, indent=2) + "\n", encoding="utf-8"
    )

    swap_env = {"PHYSICS_SCENE_DIR": str(swap_root)}
    if REPORT.exists():
        REPORT.unlink()
    if _run(swap_env):
        _copy(REPORT_SWAP)
    if REPORT.exists():
        REPORT.unlink()
    if _run(swap_env):
        _copy(REPORT_SWAP_SECOND)

    probe_root = Path("/tmp/physics-probe-scene07")
    if probe_root.exists():
        shutil.rmtree(probe_root)
    probe_root.mkdir(parents=True)
    shutil.copytree(SCENARIO_DIR, probe_root, dirs_exist_ok=True)
    probe_data = json.loads((SCENARIO_DIR / "scene_04.json").read_text(encoding="utf-8"))
    probe_data["scene_id"] = "scene_07"
    (probe_root / "scene_07.json").write_text(
        json.dumps(probe_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(probe_root)}):
        _copy(REPORT_PROBE7)

    symlink_root = Path("/tmp/physics-symlink-root")
    if symlink_root.exists() or symlink_root.is_symlink():
        symlink_root.unlink()
    symlink_root.symlink_to(SCENARIO_DIR, target_is_directory=True)
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(symlink_root.resolve())}):
        _copy(REPORT_SYMLINK)

    def _fixture_root(name: str) -> Path:
        root = Path(f"/tmp/physics-fixture-{name}")
        if root.exists():
            shutil.rmtree(root)
        shutil.copytree(SCENARIO_DIR, root, dirs_exist_ok=True)
        return root

    tol_root = _fixture_root("tolerance")
    tol_data = json.loads((tol_root / "scene_02.json").read_text(encoding="utf-8"))
    tol_data["frames"][0]["contacts"][0]["penetration_m"] = 0.00105
    (tol_root / "scene_02.json").write_text(json.dumps(tol_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(tol_root)}):
        _copy(REPORT_TOLERANCE)

    bp_root = _fixture_root("broadphase-order")
    bp_data = json.loads((bp_root / "scene_16.json").read_text(encoding="utf-8"))
    bp_data["frames"][0]["broadphase"] = [["B", "A"]]
    (bp_root / "scene_16.json").write_text(json.dumps(bp_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(bp_root)}):
        _copy(REPORT_BP_REVERSED)

    dedup_root = _fixture_root("dedupe")
    dedup_data = json.loads((dedup_root / "scene_01.json").read_text(encoding="utf-8"))
    contact = dedup_data["frames"][0]["contacts"][0]
    dedup_data["frames"][0]["contacts"] = [contact, dict(contact)]
    (dedup_root / "scene_01.json").write_text(json.dumps(dedup_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(dedup_root)}):
        _copy(REPORT_DEDUP)

    trunc_root = _fixture_root("truncated-stress")
    trunc_data = json.loads((trunc_root / "scene_13.json").read_text(encoding="utf-8"))
    trunc_data["stress"]["schedules"][0]["frame_order"] = [0, 99]
    (trunc_root / "scene_13.json").write_text(json.dumps(trunc_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(trunc_root)}):
        _copy(REPORT_TRUNC)

    over_root = _fixture_root("over-tolerance")
    over_data = json.loads((over_root / "scene_02.json").read_text(encoding="utf-8"))
    over_data["frames"][0]["contacts"][0]["penetration_m"] = 0.00115
    (over_root / "scene_02.json").write_text(json.dumps(over_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(over_root)}):
        _copy(REPORT_OVER_TOL)

    boundary_root = _fixture_root("exact-boundary")
    boundary_data = json.loads((boundary_root / "scene_02.json").read_text(encoding="utf-8"))
    boundary_data["frames"][0]["contacts"][0]["penetration_m"] = 0.0011
    (boundary_root / "scene_02.json").write_text(
        json.dumps(boundary_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(boundary_root)}):
        _copy(REPORT_BOUNDARY)

    rest_root = _fixture_root("restitution-separating")
    rest_data = json.loads((rest_root / "scene_02.json").read_text(encoding="utf-8"))
    rest_data["frames"][0]["contacts"][0]["restitution"] = 0.6
    rest_data["frames"][0]["velocities"] = {"A": [0.0, 0.2], "B": [0.0, -0.1]}
    (rest_root / "scene_02.json").write_text(json.dumps(rest_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(rest_root)}):
        _copy(REPORT_RESTSEP)

    empty_root = _fixture_root("empty-contacts")
    empty_data = json.loads((empty_root / "scene_06.json").read_text(encoding="utf-8"))
    for frame in empty_data["frames"]:
        frame["contacts"] = []
    (empty_root / "scene_06.json").write_text(json.dumps(empty_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(empty_root)}):
        _copy(REPORT_EMPTY06)

    reorder_root = _fixture_root("contact-reorder")
    reorder_data = json.loads((reorder_root / "scene_05.json").read_text(encoding="utf-8"))
    reorder_data["frames"][0]["contacts"] = list(reversed(reorder_data["frames"][0]["contacts"]))
    (reorder_root / "scene_05.json").write_text(
        json.dumps(reorder_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(reorder_root)}):
        _copy(REPORT_REORDER05)

    fmt_root = _fixture_root("format-version")
    fmt_data = json.loads((fmt_root / "scene_02.json").read_text(encoding="utf-8"))
    fmt_data["format_version"] = 2
    fmt_data["reserved"] = 7
    (fmt_root / "scene_02.json").write_text(json.dumps(fmt_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(fmt_root)}):
        _copy(REPORT_FMTVER)

    nested_root = _fixture_root("nested-decoy")
    nested_sub = nested_root / "subdir"
    nested_sub.mkdir()
    decoy_scene = {
        "scene_id": "scene_21",
        "bodies": {"X": {"layer": 1, "mass": 1.0, "sleeping": False}},
        "layers": {"1": 1},
        "frames": [],
    }
    (nested_sub / "scene_21.json").write_text(json.dumps(decoy_scene, indent=2) + "\n", encoding="utf-8")
    (nested_root / "scene_88.json").write_text(json.dumps(decoy_scene, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(nested_root)}):
        _copy(REPORT_NESTED)

    full10_root = _fixture_root("full-stress-10")
    full10_data = json.loads((full10_root / "scene_10.json").read_text(encoding="utf-8"))
    full10_data["stress"] = {"schedules": [{"schedule_id": "s1", "frame_order": [0, 1, 2, 3, 4]}]}
    (full10_root / "scene_10.json").write_text(json.dumps(full10_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(full10_root)}):
        _copy(REPORT_FULL10)

    rev03_root = _fixture_root("frames-reordered")
    rev03_data = json.loads((rev03_root / "scene_03.json").read_text(encoding="utf-8"))
    rev03_data["frames"] = list(reversed(rev03_data["frames"]))
    (rev03_root / "scene_03.json").write_text(json.dumps(rev03_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(rev03_root)}):
        _copy(REPORT_REV03)

    semi_root = _fixture_root("semicolon-body")
    semi_data = json.loads((semi_root / "scene_02.json").read_text(encoding="utf-8"))
    semi_data["bodies"]["A;cmd"] = semi_data["bodies"].pop("A")
    semi_fr = semi_data["frames"][0]
    semi_fr["contacts"][0]["body_a"] = "A;cmd"
    semi_fr["positions"]["A;cmd"] = semi_fr["positions"].pop("A")
    semi_fr["velocities"]["A;cmd"] = semi_fr["velocities"].pop("A")
    semi_fr["broadphase"] = [["A;cmd", "B"]]
    semi_fr["narrowphase"] = [["A;cmd", "B"]]
    (semi_root / "scene_02.json").write_text(json.dumps(semi_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(semi_root)}):
        _copy(REPORT_SEMI)

    dupcid_root = _fixture_root("duplicate-contact-id")
    dupcid_data = json.loads((dupcid_root / "scene_01.json").read_text(encoding="utf-8"))
    dup_contact = dict(dupcid_data["frames"][0]["contacts"][0])
    dup_contact["body_a"], dup_contact["body_b"] = "X", "Y"
    dupcid_data["frames"][0]["contacts"].append(dup_contact)
    (dupcid_root / "scene_01.json").write_text(json.dumps(dupcid_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(dupcid_root)}):
        _copy(REPORT_DUPCID)

    capture_root = _fixture_root("capture-metadata")
    capture_data = json.loads((capture_root / "scene_02.json").read_text(encoding="utf-8"))
    capture_data["capture_checksum"] = "deadbeef"
    capture_data["payload_len"] = 42
    (capture_root / "scene_02.json").write_text(json.dumps(capture_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(capture_root)}):
        _copy(REPORT_CAPTURE)

    emptstress_root = _fixture_root("empty-stress-order")
    emptstress_data = json.loads((emptstress_root / "scene_13.json").read_text(encoding="utf-8"))
    emptstress_data["stress"]["schedules"][0]["frame_order"] = []
    (emptstress_root / "scene_13.json").write_text(
        json.dumps(emptstress_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(emptstress_root)}):
        _copy(REPORT_EMPTSTRESS)

    multi13_root = _fixture_root("mixed-stress-13")
    multi13_data = json.loads((multi13_root / "scene_13.json").read_text(encoding="utf-8"))
    multi13_data["stress"]["schedules"].append({"schedule_id": "s2", "frame_order": [0, 1]})
    (multi13_root / "scene_13.json").write_text(json.dumps(multi13_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(multi13_root)}):
        _copy(REPORT_MULTI13)

    tunsub_root = _fixture_root("tunneling-sub-limit")
    tunsub_data = json.loads((tunsub_root / "scene_18.json").read_text(encoding="utf-8"))
    tunsub_data["frames"][1]["positions"]["A"] = [0.5, 1.0]
    (tunsub_root / "scene_18.json").write_text(json.dumps(tunsub_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(tunsub_root)}):
        _copy(REPORT_TUNSUB)

    btick_root = _fixture_root("backtick-body")
    btick_data = json.loads((btick_root / "scene_02.json").read_text(encoding="utf-8"))
    btick_data["bodies"]["A`x`"] = btick_data["bodies"].pop("A")
    btick_fr = btick_data["frames"][0]
    btick_fr["contacts"][0]["body_a"] = "A`x`"
    btick_fr["positions"]["A`x`"] = btick_fr["positions"].pop("A")
    btick_fr["velocities"]["A`x`"] = btick_fr["velocities"].pop("A")
    btick_fr["broadphase"] = [["A`x`", "B"]]
    btick_fr["narrowphase"] = [["A`x`", "B"]]
    (btick_root / "scene_02.json").write_text(json.dumps(btick_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(btick_root)}):
        _copy(REPORT_BTICK)

    dupframe_root = _fixture_root("duplicate-frame-index")
    dupframe_data = json.loads((dupframe_root / "scene_03.json").read_text(encoding="utf-8"))
    dup_entry = json.loads(json.dumps(dupframe_data["frames"][0]))
    dup_entry["contacts"] = [dict(dup_entry["contacts"][0])]
    dup_entry["contacts"][0]["penetration_m"] = 0.0001
    dupframe_data["frames"].insert(0, dup_entry)
    (dupframe_root / "scene_03.json").write_text(
        json.dumps(dupframe_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(dupframe_root)}):
        _copy(REPORT_DUPFRAME)

    horzn_root = _fixture_root("horizontal-normal-restitution")
    horzn_data = json.loads((horzn_root / "scene_02.json").read_text(encoding="utf-8"))
    horzn_data["frames"][0]["contacts"][0]["restitution"] = 0.6
    horzn_data["frames"][0]["contacts"][0]["normal_y"] = 0.3
    horzn_data["frames"][0]["velocities"] = {"A": [0.0, 0.2], "B": [0.0, -0.1]}
    (horzn_root / "scene_02.json").write_text(json.dumps(horzn_data, indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(horzn_root)}):
        _copy(REPORT_HORZN)

    restonce_root = _fixture_root("restitution-once-per-pair")
    restonce_data = json.loads((restonce_root / "scene_02.json").read_text(encoding="utf-8"))
    restonce_data["frames"][0]["contacts"][0]["restitution"] = 0.6
    restonce_data["frames"][0]["velocities"] = {"A": [0.0, 0.2], "B": [0.0, -0.1]}
    second_contact = dict(restonce_data["frames"][0]["contacts"][0])
    second_contact["contact_id"] = "c2"
    restonce_data["frames"][0]["contacts"].append(second_contact)
    (restonce_root / "scene_02.json").write_text(
        json.dumps(restonce_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(restonce_root)}):
        _copy(REPORT_RESTONCE)

    sleepover_root = _fixture_root("sleep-diagonal-over")
    sleepover_data = json.loads((sleepover_root / "scene_19.json").read_text(encoding="utf-8"))
    sleepover_data["frames"][0]["velocities"]["A"] = [0.008, 0.008]
    (sleepover_root / "scene_19.json").write_text(
        json.dumps(sleepover_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(sleepover_root)}):
        _copy(REPORT_SLEEPOVER)

    sleepunder_root = _fixture_root("sleep-diagonal-under")
    sleepunder_data = json.loads((sleepunder_root / "scene_19.json").read_text(encoding="utf-8"))
    sleepunder_data["frames"][0]["velocities"]["A"] = [0.005, 0.005]
    sleepunder_data["frames"][0]["velocities"]["B"] = [0.0, 0.005]
    (sleepunder_root / "scene_19.json").write_text(
        json.dumps(sleepunder_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(sleepunder_root)}):
        _copy(REPORT_SLEEPUNDER)

    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(SCENARIO_DIR.resolve())}):
        _copy(REPORT_ABSPATH)

    approach_root = _fixture_root("approaching-restitution")
    approach_data = json.loads((approach_root / "scene_02.json").read_text(encoding="utf-8"))
    approach_data["frames"][0]["contacts"][0]["restitution"] = 0.6
    approach_data["frames"][0]["velocities"] = {"A": [0.0, -0.2], "B": [0.0, 0.1]}
    (approach_root / "scene_02.json").write_text(
        json.dumps(approach_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(approach_root)}):
        _copy(REPORT_APPROACH)

    swapbody_root = _fixture_root("restitution-swapped-bodies")
    swapbody_data = json.loads((swapbody_root / "scene_02.json").read_text(encoding="utf-8"))
    swap_fr = swapbody_data["frames"][0]
    swap_fr["contacts"][0]["body_a"] = "B"
    swap_fr["contacts"][0]["body_b"] = "A"
    swap_fr["contacts"][0]["restitution"] = 0.6
    swap_fr["velocities"] = {"A": [0.0, -0.1], "B": [0.0, 0.2]}
    swap_fr["broadphase"] = [["B", "A"]]
    swap_fr["narrowphase"] = [["B", "A"]]
    (swapbody_root / "scene_02.json").write_text(
        json.dumps(swapbody_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(swapbody_root)}):
        _copy(REPORT_SWAPBODY)

    missstress_root = _fixture_root("missing-only-stress")
    missstress_data = json.loads((missstress_root / "scene_13.json").read_text(encoding="utf-8"))
    missstress_data["stress"] = {
        "schedules": [{"schedule_id": "s1", "frame_order": [99, 100]}]
    }
    (missstress_root / "scene_13.json").write_text(
        json.dumps(missstress_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(missstress_root)}):
        _copy(REPORT_MISSSTRESS)

    metarest_root = _fixture_root("metadata-plus-restitution")
    metarest_data = json.loads((metarest_root / "scene_02.json").read_text(encoding="utf-8"))
    metarest_data["format_version"] = 3
    metarest_data["reserved"] = 9
    metarest_data["capture_checksum"] = "cafebabe"
    metarest_data["payload_len"] = 128
    metarest_data["frames"][0]["contacts"][0]["restitution"] = 0.6
    metarest_data["frames"][0]["velocities"] = {"A": [0.0, 0.2], "B": [0.0, -0.1]}
    (metarest_root / "scene_02.json").write_text(
        json.dumps(metarest_data, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(metarest_root)}):
        _copy(REPORT_METAREST)

    perm_root = _fixture_root("permission-denied-decoy")
    decoy_path = perm_root / "scene_99.json"
    decoy_path.write_text('{"scene_id":"scene_99","bodies":{},"layers":{},"frames":[]}\n', encoding="utf-8")
    decoy_path.chmod(0o000)
    if REPORT.exists():
        REPORT.unlink()
    if _run({"PHYSICS_SCENE_DIR": str(perm_root)}):
        _copy(REPORT_PERMDECOY)
    try:
        decoy_path.chmod(0o644)
    except OSError:
        pass

    if REPORT.exists():
        REPORT.unlink()
    _run()

    _ARTIFACTS_READY = True


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _by_id(report: dict) -> dict[str, dict]:
    return {row["scene_id"]: row for row in report["scenes"]}


def _assert_report_bytes(path: Path) -> dict:
    assert path.exists() and path.stat().st_size > 100
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    return json.loads(raw.decode("utf-8"))


def test_verifier_harness_prepared_artifacts():
    """tests/test.sh must run prepare_verifier_artifacts before pytest."""
    assert _ARTIFACTS_READY or REPORT_FIRST.exists()


def test_make_build_succeeds_and_binary_size():
    """instruction.md: make build succeeds and contact-resolver exceeds 2048 bytes."""
    result = subprocess.run(
        ["make", "build"],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert BIN.exists() and BIN.stat().st_size > 2048
    assert os.access(BIN, os.X_OK)


def test_solver_go_implementation_replaces_stub():
    """instruction.md: resolver.go must implement AnalyzeScene without stub panic text."""
    text = SOLVER_GO.read_text(encoding="utf-8")
    assert STUB_NOT_IMPLEMENTED not in text
    assert "func AnalyzeScene" in text


def test_pipeline_go_delegates_to_solver():
    """instruction.md: orchestrator loads scenes and calls solver.AnalyzeScene."""
    text = PIPELINE_GO.read_text(encoding="utf-8")
    assert "solver.AnalyzeScene" in text
    assert STUB_NOT_IMPLEMENTED not in text


def test_main_go_entrypoint_unchanged():
    """instruction.md: replay/main.go must remain the shipped entrypoint."""
    digest = hashlib.sha256(MAIN_GO.read_bytes()).hexdigest()
    assert digest == EXPECTED_MAIN_GO_SHA256
    text = MAIN_GO.read_text(encoding="utf-8")
    assert "orchestrator.Run" in text and "export.Write" in text


def test_shipped_spec_and_policy_files_unchanged():
    """instruction.md: spec files and contact_policy.yaml are SHA256 pinned."""
    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == EXPECTED_SCHEMA_SHA256
    assert hashlib.sha256(INPUT_FMT.read_bytes()).hexdigest() == EXPECTED_INPUT_FMT_SHA256
    assert hashlib.sha256(POLICY.read_bytes()).hexdigest() == EXPECTED_POLICY_SHA256


def test_report_json_key_order_is_normative():
    """OUTPUT_SCHEMA.md: nested key order for summary, scene, stress, and violation rows."""
    report = _load(REPORT)
    assert list(report.keys()) == ["summary", "scenes"]
    assert list(report["summary"].keys()) == SUMMARY_KEYS
    for row in report["scenes"]:
        assert list(row.keys()) == SCENE_KEYS
        assert list(row["stress"].keys()) == STRESS_KEYS
        for viol in row["violations"]:
            assert list(viol.keys()) == VIOLATION_KEYS


def test_summary_reconciles_with_scene_rows():
    """OUTPUT_SCHEMA.md: twelve unstable scenes, eight stable, thirteen violations total."""
    report = _load(REPORT)
    s = report["summary"]
    scenes = report["scenes"]
    assert s["scenes_analyzed"] == 20 == len(scenes)
    unstable = sum(1 for t in scenes if t["unstable"])
    stable = sum(1 for t in scenes if not t["unstable"])
    assert unstable == 12 and stable == 8
    assert s["total_violations"] == 13
    assert s["unstable_scenes"] == unstable
    assert s["stable_scenes"] == stable
    assert s["total_violations"] == sum(len(t["violations"]) for t in scenes)
    assert s["stress_replays_run"] == sum(t["stress"]["replays_run"] for t in scenes)
    assert s["stress_replays_passed"] == sum(t["stress"]["replays_passed"] for t in scenes)


def test_bundled_scene_unstable_flags():
    """OUTPUT_SCHEMA.md bundled table: unstable verdict for scene_01 through scene_20."""
    by_id = _by_id(_load(REPORT))
    for sid, want in EXPECTED_UNSTABLE.items():
        assert by_id[sid]["unstable"] is want, sid


def test_bundled_per_scene_violation_kinds_and_chain_len():
    """OUTPUT_SCHEMA.md per-scene table: violation kinds and impulse_chain_len per scene."""
    by_id = _by_id(_load(REPORT))
    for sid in EXPECTED_SCENE_IDS:
        row = by_id[sid]
        kinds = {v["kind"] for v in row["violations"]}
        assert kinds == EXPECTED_VIOLATION_KINDS[sid], sid
        assert row["impulse_chain_len"] == EXPECTED_IMPULSE_CHAIN_LEN[sid], sid


def test_bundled_violation_records_match_oracle_table():
    """OUTPUT_SCHEMA.md bundled violation records: kind, frame, bodies, detail per scene."""
    by_id = _by_id(_load(REPORT))
    for sid in EXPECTED_SCENE_IDS:
        got = by_id[sid]["violations"]
        want = EXPECTED_VIOLATION_RECORDS.get(sid, [])
        assert len(got) == len(want), sid
        for g, w in zip(got, want, strict=True):
            assert g == w, sid


def test_bundled_stress_validated_flags():
    """OUTPUT_SCHEMA.md stress tallies: validated flags for all twenty scenes."""
    by_id = _by_id(_load(REPORT))
    for sid, want in EXPECTED_STRESS_VALIDATED.items():
        assert by_id[sid]["stress"]["validated"] is want, sid


def test_bundled_max_penetration_m_per_scene():
    """OUTPUT_SCHEMA.md bundled max_penetration_m table for scene_01 through scene_20."""
    by_id = _by_id(_load(REPORT))
    for sid, want in EXPECTED_MAX_PENETRATION.items():
        assert by_id[sid]["max_penetration_m"] == want, sid


def test_bundled_stress_replay_tallies_on_scheduled_scenes():
    """OUTPUT_SCHEMA.md bundled stress replay tallies for scene_10, scene_13, scene_14."""
    by_id = _by_id(_load(REPORT))
    for sid, want in EXPECTED_STRESS_TALLIES.items():
        assert by_id[sid]["stress"] == want, sid
    for sid in EXPECTED_SCENE_IDS:
        if sid in EXPECTED_STRESS_TALLIES:
            continue
        stress = by_id[sid]["stress"]
        assert stress == {"replays_run": 0, "replays_passed": 0, "validated": True}, sid


def test_physics_scene_dir_symlink_produces_identical_report():
    """OUTPUT_SCHEMA.md symlink fixture: absolute symlinked root matches default bundled bytes."""
    assert REPORT_SYMLINK.exists()
    assert REPORT_FIRST.read_bytes() == REPORT_SYMLINK.read_bytes()


def test_physics_scene_dir_decoy_scene_99_ignored():
    """OUTPUT_SCHEMA.md decoy fixture: scene_99.json does not affect scenes_analyzed or rows."""
    assert REPORT_SWAP.exists()
    report = _load(REPORT_SWAP)
    assert report["summary"]["scenes_analyzed"] == 20
    assert len(report["scenes"]) == 20
    assert all(row["scene_id"] in EXPECTED_SCENE_IDS for row in report["scenes"])
    assert not any(row["scene_id"] == "scene_99" for row in report["scenes"])


def test_penetration_tolerance_boundary_below_max_plus_tolerance():
    """OUTPUT_SCHEMA.md tolerance fixture: scene_02 at 0.00105 m stays stable with no violations."""
    assert REPORT_TOLERANCE.exists()
    row = _by_id(_load(REPORT_TOLERANCE))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []
    assert row["max_penetration_m"] == 0.00105


def test_broadphase_reversed_pair_order_matches_direct_order():
    """OUTPUT_SCHEMA.md broadphase_order fixture: reversed A/B pair clears scene_16 phase_mismatch."""
    assert REPORT_BP_REVERSED.exists()
    row = _by_id(_load(REPORT_BP_REVERSED))["scene_16"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_duplicate_contact_violations_deduped_to_single_row():
    """OUTPUT_SCHEMA.md dedupe fixture: identical contacts emit one penetration_artifact row."""
    assert REPORT_DEDUP.exists()
    row = _by_id(_load(REPORT_DEDUP))["scene_01"]
    assert row["unstable"] is True
    assert len(row["violations"]) == 1
    assert row["violations"][0]["kind"] == "penetration_artifact"


def test_stress_truncated_frame_order_skips_missing_indices():
    """OUTPUT_SCHEMA.md truncated_stress fixture: unknown frame indices force validated false."""
    assert REPORT_TRUNC.exists()
    row = _by_id(_load(REPORT_TRUNC))["scene_13"]
    assert row["unstable"] is True
    assert any(v["kind"] == "layer_filter_miss" for v in row["violations"])
    assert row["stress"]["replays_run"] == 1
    assert row["stress"]["validated"] is False


def test_penetration_above_max_plus_tolerance_flags_artifact():
    """OUTPUT_SCHEMA.md over_tolerance fixture: 0.00115 m penetration emits formatted detail."""
    assert REPORT_OVER_TOL.exists()
    row = _by_id(_load(REPORT_OVER_TOL))["scene_02"]
    assert row["unstable"] is True
    assert row["violations"] == [
        {
            "kind": "penetration_artifact",
            "frame": 0,
            "bodies": ["A", "B"],
            "detail": "penetration 0.0011 m",
        }
    ]
    assert row["max_penetration_m"] == 0.00115


def test_penetration_at_max_plus_tolerance_exact_boundary_stable():
    """OUTPUT_SCHEMA.md exact_boundary fixture: penetration exactly 0.0011 m stays stable."""
    assert REPORT_BOUNDARY.exists()
    row = _by_id(_load(REPORT_BOUNDARY))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []
    assert row["max_penetration_m"] == 0.0011


def test_restitution_separating_velocity_detail_on_fixture():
    """OUTPUT_SCHEMA.md restitution_separating fixture: separating normal velocity detail string."""
    assert REPORT_RESTSEP.exists()
    row = _by_id(_load(REPORT_RESTSEP))["scene_02"]
    assert row["unstable"] is True
    assert len(row["violations"]) == 1
    viol = row["violations"][0]
    assert viol["kind"] == "restitution_violation"
    assert viol["frame"] == 0
    assert viol["bodies"] == ["A", "B"]
    assert viol["detail"] == "separating normal velocity with positive restitution"


def test_horizontal_normal_suppresses_separating_restitution():
    """OUTPUT_SCHEMA.md horizontal_normal fixture: normal_y <= 0.5 skips separating restitution check."""
    assert REPORT_HORZN.exists()
    row = _by_id(_load(REPORT_HORZN))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_restitution_separating_emitted_once_per_unordered_body_pair():
    """OUTPUT_SCHEMA.md restitution_once_per_pair fixture: duplicate A-B contacts emit one separating row."""
    assert REPORT_RESTONCE.exists()
    row = _by_id(_load(REPORT_RESTONCE))["scene_02"]
    assert row["unstable"] is True
    separating = [v for v in row["violations"] if v["kind"] == "restitution_violation"]
    assert len(separating) == 1
    assert separating[0]["detail"] == "separating normal velocity with positive restitution"


def test_sleep_diagonal_velocity_above_threshold_triggers_activation():
    """OUTPUT_SCHEMA.md sleep_diagonal_over fixture: hypot(vx, vy) above threshold flags sleeping body."""
    assert REPORT_SLEEPOVER.exists()
    row = _by_id(_load(REPORT_SLEEPOVER))["scene_19"]
    assert row["unstable"] is True
    sleep_v = [v for v in row["violations"] if v["kind"] == "sleep_activation_error"]
    assert len(sleep_v) == 1
    assert sleep_v[0]["bodies"] == ["A"]


def test_sleep_diagonal_velocity_below_threshold_stays_stable():
    """OUTPUT_SCHEMA.md sleep_diagonal_under fixture: hypot(vx, vy) at or below threshold stays stable."""
    assert REPORT_SLEEPUNDER.exists()
    row = _by_id(_load(REPORT_SLEEPUNDER))["scene_19"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_physics_scene_dir_absolute_path_produces_identical_report():
    """OUTPUT_SCHEMA.md absolute_path fixture: resolved PHYSICS_SCENE_DIR matches default bundled bytes."""
    assert REPORT_ABSPATH.exists()
    assert REPORT_FIRST.read_bytes() == REPORT_ABSPATH.read_bytes()


def test_approaching_normal_velocity_does_not_emit_separating_restitution():
    """OUTPUT_SCHEMA.md approaching_restitution fixture: negative relative normal velocity stays stable."""
    assert REPORT_APPROACH.exists()
    row = _by_id(_load(REPORT_APPROACH))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_restitution_uses_contact_body_a_body_b_velocity_keys():
    """OUTPUT_SCHEMA.md restitution_swapped_bodies fixture: body_a=B body_b=A still separates correctly."""
    assert REPORT_SWAPBODY.exists()
    row = _by_id(_load(REPORT_SWAPBODY))["scene_02"]
    assert row["unstable"] is True
    viol = [v for v in row["violations"] if v["kind"] == "restitution_violation"]
    assert len(viol) == 1
    assert viol[0]["bodies"] == ["B", "A"]
    assert viol[0]["detail"] == "separating normal velocity with positive restitution"


def test_stress_frame_order_all_missing_indices_forces_validated_false():
    """OUTPUT_SCHEMA.md missing_only_stress fixture: [99,100] skips replay frames but declared span invalidates."""
    assert REPORT_MISSSTRESS.exists()
    row = _by_id(_load(REPORT_MISSSTRESS))["scene_13"]
    assert row["unstable"] is True
    assert row["stress"]["replays_run"] == 1
    assert row["stress"]["replays_passed"] == 1
    assert row["stress"]["validated"] is False


def test_optional_metadata_does_not_suppress_separating_restitution():
    """OUTPUT_SCHEMA.md metadata_plus_restitution fixture: format_version/payload_len ignored, separating still fires."""
    assert REPORT_METAREST.exists()
    row = _by_id(_load(REPORT_METAREST))["scene_02"]
    assert row["unstable"] is True
    viol = row["violations"]
    assert len(viol) == 1
    assert viol[0]["kind"] == "restitution_violation"
    assert viol[0]["detail"] == "separating normal velocity with positive restitution"


def test_permission_denied_decoy_scene_does_not_break_bundled_report():
    """OUTPUT_SCHEMA.md permission_denied_decoy fixture: unreadable scene_99 ignored; summary matches bundled."""
    assert REPORT_PERMDECOY.exists()
    report = _load(REPORT_PERMDECOY)
    assert report["summary"]["scenes_analyzed"] == 20
    assert "scene_99" not in _by_id(report)
    assert REPORT_FIRST.read_bytes() == REPORT_PERMDECOY.read_bytes()


def test_tunneling_sub_limit_displacement_stable():
    """OUTPUT_SCHEMA.md tunneling_sub_limit fixture: displacement below policy limit stays stable."""
    assert REPORT_TUNSUB.exists()
    row = _by_id(_load(REPORT_TUNSUB))["scene_18"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_backtick_body_id_literal_preserved_in_scene_rows():
    """OUTPUT_SCHEMA.md backtick_body_id fixture: body id containing backticks stays stable."""
    assert REPORT_BTICK.exists()
    row = _by_id(_load(REPORT_BTICK))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_duplicate_frame_index_entries_use_array_order_for_stacking():
    """OUTPUT_SCHEMA.md duplicate_frame_index fixture: repeated frame numbers follow frames[] order."""
    assert REPORT_DUPFRAME.exists()
    row = _by_id(_load(REPORT_DUPFRAME))["scene_03"]
    assert row["unstable"] is True
    stacking = [v for v in row["violations"] if v["kind"] == "stacking_instability"]
    assert len(stacking) == 2
    assert [s["frame"] for s in stacking] == [1, 2]


def test_impulse_chain_len_zero_when_all_frames_have_no_contacts():
    """OUTPUT_SCHEMA.md empty_contacts fixture: zero chain length and zero max penetration."""
    assert REPORT_EMPTY06.exists()
    row = _by_id(_load(REPORT_EMPTY06))["scene_06"]
    assert row["unstable"] is False
    assert row["impulse_chain_len"] == 0
    assert row["max_penetration_m"] == 0.0


def test_reordered_contact_ids_preserve_impulse_chain_len():
    """OUTPUT_SCHEMA.md contact_reorder fixture: contact_id sort keeps chain length and bodies."""
    assert REPORT_REORDER05.exists()
    row = _by_id(_load(REPORT_REORDER05))["scene_05"]
    assert row["impulse_chain_len"] == 2
    assert row["violations"][0]["bodies"] == ["A", "C"]


def test_format_version_and_reserved_fields_do_not_change_scene_02():
    """OUTPUT_SCHEMA.md format_version fixture: optional metadata ignored for replay."""
    assert REPORT_FMTVER.exists()
    row = _by_id(_load(REPORT_FMTVER))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_nested_subdirectory_and_extra_scene_files_ignored():
    """OUTPUT_SCHEMA.md nested_decoy fixture: only scene_01..scene_20 analyzed."""
    assert REPORT_NESTED.exists()
    report = _load(REPORT_NESTED)
    assert report["summary"]["scenes_analyzed"] == 20
    assert report["summary"]["unstable_scenes"] == 12
    assert report["summary"]["total_violations"] == 13
    ids = {row["scene_id"] for row in report["scenes"]}
    assert ids == set(EXPECTED_SCENE_IDS)


def test_stress_full_frame_span_on_scene_10_fixture_validated_false():
    """OUTPUT_SCHEMA.md full_stress_scene_10 fixture: full replay span forces validated false."""
    assert REPORT_FULL10.exists()
    row = _by_id(_load(REPORT_FULL10))["scene_10"]
    assert row["unstable"] is True
    assert any(v["kind"] == "stale_manifold" for v in row["violations"])
    assert row["stress"]["replays_run"] == 1
    assert row["stress"]["validated"] is False


def test_stacking_instability_emitted_only_once_at_third_frame():
    """OUTPUT_SCHEMA.md bundled scene_03: single stacking_instability on frame 2 only."""
    row = _by_id(_load(REPORT))["scene_03"]
    stacking = [v for v in row["violations"] if v["kind"] == "stacking_instability"]
    assert len(stacking) == 1
    assert stacking[0]["frame"] == 2


def test_frames_json_array_order_controls_stacking_detection():
    """OUTPUT_SCHEMA.md frames_reordered fixture: reversed frames[] clears scene_03 stacking."""
    assert REPORT_REV03.exists()
    row = _by_id(_load(REPORT_REV03))["scene_03"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_body_ids_with_semicolons_preserved_in_scene_rows():
    """OUTPUT_SCHEMA.md semicolon_body_id fixture: literal body id with semicolon stays stable."""
    assert REPORT_SEMI.exists()
    row = _by_id(_load(REPORT_SEMI))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_duplicate_contact_id_emits_separate_violations():
    """OUTPUT_SCHEMA.md duplicate_contact_id fixture: shared contact_id on different pairs."""
    assert REPORT_DUPCID.exists()
    row = _by_id(_load(REPORT_DUPCID))["scene_01"]
    assert row["unstable"] is True
    assert len(row["violations"]) == 2
    kinds = {v["kind"] for v in row["violations"]}
    assert kinds == {"penetration_artifact"}
    body_pairs = {tuple(v["bodies"]) for v in row["violations"]}
    assert body_pairs == {("A", "B"), ("X", "Y")}


def test_optional_capture_checksum_and_payload_len_ignored():
    """OUTPUT_SCHEMA.md capture_metadata fixture: optional checksum fields do not change replay."""
    assert REPORT_CAPTURE.exists()
    row = _by_id(_load(REPORT_CAPTURE))["scene_02"]
    assert row["unstable"] is False
    assert row["violations"] == []


def test_empty_stress_frame_order_schedule_passes():
    """OUTPUT_SCHEMA.md empty_stress_order fixture: [] frame_order keeps validated true."""
    assert REPORT_EMPTSTRESS.exists()
    row = _by_id(_load(REPORT_EMPTSTRESS))["scene_13"]
    assert row["stress"]["replays_run"] == 1
    assert row["stress"]["replays_passed"] == 1
    assert row["stress"]["validated"] is True


def test_mixed_stress_schedules_prefix_and_full_keeps_validated_true():
    """OUTPUT_SCHEMA.md mixed_stress_schedules fixture: prefix plus full span stays validated."""
    assert REPORT_MULTI13.exists()
    row = _by_id(_load(REPORT_MULTI13))["scene_13"]
    assert row["stress"]["replays_run"] == 2
    assert row["stress"]["replays_passed"] == 2
    assert row["stress"]["validated"] is True


def test_bundled_summary_stress_replays_passed_total():
    """OUTPUT_SCHEMA.md bundled stress tallies: summary stress_replays_passed equals 3."""
    report = _load(REPORT)
    assert report["summary"]["stress_replays_passed"] == 3
    assert report["summary"]["stress_replays_run"] == 3


def test_impulse_chain_break_scene_05_chained_contacts():
    """INPUT_FORMAT.md: chained impulse contacts must detect sub-minimum transfer on A-B-C stack."""
    row = _by_id(_load(REPORT))["scene_05"]
    assert row["unstable"] and row["impulse_chain_len"] == 2
    kinds = {v["kind"] for v in row["violations"]}
    assert "impulse_chain_break" in kinds


def test_stale_manifold_survives_after_contact_removal_scene_10():
    """OUTPUT_SCHEMA.md: stale_manifold when manifold outlives max_survival_frames."""
    row = _by_id(_load(REPORT))["scene_10"]
    assert row["unstable"]
    assert any(v["kind"] == "stale_manifold" for v in row["violations"])
    assert row["stress"]["validated"] is True


def test_layer_filter_miss_scene_13_and_stress_prefix_validated():
    """Bundled scene_13: layer mask violation with prefix stress replay validated true."""
    row = _by_id(_load(REPORT))["scene_13"]
    assert row["unstable"]
    assert any(v["kind"] == "layer_filter_miss" for v in row["violations"])
    assert row["stress"]["validated"] is True


def test_constraint_violation_scene_14_stress_full_replay_invalid():
    """Bundled scene_14: articulated constraint breach with full stress replay validated false."""
    row = _by_id(_load(REPORT))["scene_14"]
    assert row["unstable"]
    assert any(v["kind"] == "constraint_violation" for v in row["violations"])
    assert row["stress"]["validated"] is False


def test_tunneling_high_velocity_displacement_scene_18():
    """contact_policy.yaml tunneling threshold: scene_18 reports tunneling on frame 1."""
    row = _by_id(_load(REPORT))["scene_18"]
    assert row["unstable"]
    tunnel = [v for v in row["violations"] if v["kind"] == "tunneling"]
    assert tunnel and tunnel[0]["frame"] == 1


def test_dual_violation_penetration_and_phase_mismatch_scene_11():
    """Bundled scene_11: penetration artifact plus narrowphase not covered by broadphase."""
    row = _by_id(_load(REPORT))["scene_11"]
    assert row["unstable"] and len(row["violations"]) == 2
    kinds = {v["kind"] for v in row["violations"]}
    assert kinds == {"penetration_artifact", "phase_mismatch"}


def test_clean_scenes_emit_empty_violation_arrays():
    """OUTPUT_SCHEMA.md: stable scenes use empty violations arrays never null."""
    report = _load(REPORT)
    raw = REPORT.read_bytes().decode("utf-8")
    for row in report["scenes"]:
        if not row["unstable"]:
            assert row["violations"] == []
            tid = row["scene_id"]
            chunk = raw.split(f'"{tid}"', 1)[1].split('"scene_id"', 1)[0]
            assert '"violations": null' not in chunk


def test_physics_scene_dir_swap_changes_scene_01_not_hardcoded():
    """PHYSICS_SCENE_DIR swap: scene_02 payload under scene_01 id lowers unstable count."""
    assert REPORT_SWAP.exists()
    primary = _by_id(_load(REPORT_FIRST))
    swapped = _by_id(_load(REPORT_SWAP))
    assert primary["scene_01"]["unstable"] is True
    assert swapped["scene_01"]["unstable"] is False
    assert _load(REPORT_SWAP)["summary"]["unstable_scenes"] < _load(REPORT_FIRST)["summary"][
        "unstable_scenes"
    ]


def test_physics_scene_dir_probe_scene_07_clean():
    """PHYSICS_SCENE_DIR probe: trace_04 payload under scene_07 id is stable."""
    assert REPORT_PROBE7.exists()
    row = _by_id(_load(REPORT_PROBE7))["scene_07"]
    assert row["unstable"] is False and row["violations"] == []


def test_report_byte_identical_across_runs():
    """OUTPUT_SCHEMA.md: consecutive resolver runs must be byte identical."""
    assert REPORT_FIRST.read_bytes() == REPORT_SECOND.read_bytes()
    assert REPORT_SWAP.read_bytes() == REPORT_SWAP_SECOND.read_bytes()


def test_bundled_scenario_sha256_checksums():
    """instruction.md: each /app/scenarios/scene_*.json SHA256 matches bundled manifest."""
    for name, want in BUNDLED_DATA_CHECKSUMS.items():
        digest = hashlib.sha256((SCENARIO_DIR / name).read_bytes()).hexdigest()
        assert digest == want, name


def test_solver_must_not_embed_oracle_digests():
    """Anti-cheating: solver source must not embed verifier checksums or artifact paths."""
    text = SOLVER_GO.read_text(encoding="utf-8")
    for digest in BUNDLED_DATA_CHECKSUMS.values():
        assert digest not in text
    assert "PHYSICS_VERIFIER_ARTIFACT_DIR" not in text


def test_contact_policy_yaml_governs_thresholds():
    """contact_policy.yaml shipped values drive penetration, impulse, and layer rules."""
    rules = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    assert rules["resolution"]["max_penetration_m"] == 0.001
    assert rules["impulse"]["chain_min_transfer"] == 0.1
    assert rules["layers"]["enforce_mask"] is True
    assert rules["manifolds"]["max_survival_frames"] == 2
    assert rules["tunneling"]["velocity_threshold_m_s"] == 50.0
