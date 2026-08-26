from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


TASK = Path("/app/task_file")
INPUT = TASK / "beamline_case.json"
OUTPUT = TASK / "output"
SOURCE = Path("/app/main.js")
BIN = TASK / "beamline-tuner"

INPUT_HASH = "6781cd7c00e1a642e25b66bea4021ae09bbc1971f4c8e9bc9214a52f9f9c3eae"
OUT_FILES = ["beam_plan.json", "profile_screen.json", "thermal_trace.json"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r2(value: float) -> float:
    return round(value + 1e-9, 2)


def centi(value: float) -> int:
    return int(math.floor(value * 100 + 0.5 + 1e-7))


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in rows}


def load_case(path: Path = INPUT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def profile_single(case: dict, profile: dict) -> dict:
    protons = case["protons_per_spill"]
    horns = by_id(case["horns"])
    heat = {hid: profile["heat_mj"].get(hid, 0.0) * protons for hid in horns}
    flux = {b["id"]: profile["flux"].get(b["id"], 0.0) * b["response"] * protons for b in case["bins"]}
    dose = profile["shield_dose"] * protons
    window_heat = sum(heat.values()) + case["cooldown_reserve_mj"]
    blockers = []
    if window_heat > case["max_window_heat_mj"] + 1e-9:
        blockers.append("window_heat")
    for horn in case["horns"]:
        if abs(profile["currents_ka"].get(horn["id"], 0.0)) > horn["current_limit_ka"] + 1e-9:
            blockers.append(f"current:{horn['id']}")
    return {
        "profile_id": profile["id"],
        "bin_flux": [{"bin": bid, "flux": r2(flux[bid])} for bid in sorted(flux)],
        "horn_heat_mj": [{"horn": hid, "heat_mj": r2(heat[hid])} for hid in sorted(heat)],
        "shield_dose": r2(dose),
        "window_heat_mj": r2(window_heat),
        "feasible": not blockers,
        "blockers": sorted(blockers),
    }


def profile_screen(case: dict) -> list[dict]:
    return [profile_single(case, p) for p in sorted(case["profiles"], key=lambda r: r["id"])]


def transition_ok(case: dict, prev: dict, cur: dict) -> bool:
    for horn in case["horns"]:
        hid = horn["id"]
        a = prev["currents_ka"].get(hid, 0.0)
        b = cur["currents_ka"].get(hid, 0.0)
        if abs(a) > 1e-9 and abs(b) > 1e-9 and abs(a - b) > case["max_current_delta_ka"] + 1e-9:
            return False
    return True


def evaluate(case: dict, ids: tuple[str, ...]) -> tuple[bool, dict, list[str]]:
    profiles = by_id(case["profiles"])
    horns = by_id(case["horns"])
    temps = {hid: horn["base_temp_k"] for hid, horn in horns.items()}
    totals = {b["id"]: 0.0 for b in case["bins"]}
    dose = 0.0
    rows = []
    blockers = []
    peak_temp = max(temps.values())
    prior = None
    changes = 0

    for slot, pid in enumerate(ids, start=1):
        prof = profiles[pid]
        if prior is not None:
            if not transition_ok(case, prior, prof):
                blockers.append(f"current_delta:{slot}")
            if pid != prior["id"] and pid != "idle" and prior["id"] != "idle":
                changes += 1
        prior = prof

        for horn in case["horns"]:
            hid = horn["id"]
            temps[hid] = max(horn["base_temp_k"], temps[hid] - horn["cool_rate_k"])

        single = profile_single(case, prof)
        if not single["feasible"]:
            blockers.extend(single["blockers"])
        dose += prof["shield_dose"] * case["protons_per_spill"]
        for binrow in case["bins"]:
            bid = binrow["id"]
            totals[bid] += prof["flux"].get(bid, 0.0) * binrow["response"] * case["protons_per_spill"]
        for horn in case["horns"]:
            hid = horn["id"]
            heat = prof["heat_mj"].get(hid, 0.0) * case["protons_per_spill"]
            temps[hid] += heat / horn["thermal_capacity_mj_per_k"]
            peak_temp = max(peak_temp, temps[hid])
            if temps[hid] > case["max_horn_temp_k"] + 1e-9:
                blockers.append(f"horn_temp:{hid}")
        if dose > case["max_shield_dose"] + 1e-9:
            blockers.append("shield_dose")
        rows.append(
            {
                "slot": slot,
                "profile_id": pid,
                "horn_temps_k": [{"horn": hid, "temp_k": r2(temps[hid])} for hid in sorted(temps)],
                "cumulative_flux": [{"bin": bid, "flux": r2(totals[bid])} for bid in sorted(totals)],
                "cumulative_shield_dose": r2(dose),
            }
        )

    under = 0.0
    over = 0.0
    for b in case["bins"]:
        actual = totals[b["id"]]
        target = b["min_flux"]
        if actual + 1e-9 < target:
            under += target - actual
            blockers.append(f"flux:{b['id']}")
        else:
            over += actual - target

    signature = "|".join(f"{i + 1}:{pid}" for i, pid in enumerate(ids))
    objective = [centi(under), centi(over), centi(peak_temp), centi(dose), changes, signature]
    payload = {
        "ids": ids,
        "rows": rows,
        "totals": [{"bin": bid, "flux": r2(totals[bid])} for bid in sorted(totals)],
        "dose": r2(dose),
        "peak_temp_k": r2(peak_temp),
        "objective": objective,
    }
    return not blockers, payload, sorted(set(blockers))


def reference(case: dict) -> dict:
    screen = profile_screen(case)
    feasible = [row["profile_id"] for row in screen if row["feasible"]]
    if not feasible:
        return blocked(screen, ["no_screen_profile"])
    best = None
    best_payload = None
    all_blockers: set[str] = set()
    for combo in itertools.product(sorted(feasible), repeat=case["spill_count"]):
        ok, payload, blockers = evaluate(case, combo)
        if not ok:
            all_blockers.update(blockers)
            continue
        if best is None or payload["objective"] < best:
            best = payload["objective"]
            best_payload = payload
    if best_payload is None:
        return blocked(screen, sorted(all_blockers) or ["no_valid_schedule"])
    return {
        "beam_plan.json": {
            "status": "ok",
            "objective": best_payload["objective"],
            "assignments": [{"slot": i + 1, "profile_id": pid} for i, pid in enumerate(best_payload["ids"])],
            "blockers": [],
        },
        "profile_screen.json": {"profiles": screen},
        "thermal_trace.json": {
            "slots": best_payload["rows"],
            "final_flux": best_payload["totals"],
            "peak_temp_k": best_payload["peak_temp_k"],
            "shield_dose": best_payload["dose"],
        },
    }


def blocked(screen: list[dict], blockers: list[str]) -> dict:
    return {
        "beam_plan.json": {"status": "blocked", "objective": [], "assignments": [], "blockers": sorted(blockers)},
        "profile_screen.json": {"profiles": screen},
        "thermal_trace.json": {"slots": [], "final_flux": [], "peak_temp_k": 0.0, "shield_dose": 0.0},
    }


def write_case(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_calculation(input_path: Path = INPUT, output_dir: Path = OUTPUT) -> dict:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if input_path == INPUT:
        subprocess.run(["node", str(SOURCE)], cwd="/tmp", check=True, timeout=30)
    else:
        subprocess.run(["node", str(SOURCE), str(input_path), str(output_dir)], cwd="/tmp", check=True, timeout=30)
    assert sorted(p.name for p in output_dir.iterdir() if p.is_file()) == OUT_FILES
    return {name: json.loads((output_dir / name).read_text(encoding="utf-8")) for name in OUT_FILES}


def assert_match(case: dict, input_path: Path = INPUT, output_dir: Path = OUTPUT) -> dict:
    actual = run_calculation(input_path, output_dir)
    expected = reference(case)
    assert actual == expected
    return actual


def variant(base: dict, name: str) -> dict:
    data = copy.deepcopy(base)
    if name == "dose_cap_forces_wide_trim_mix":
        data["max_shield_dose"] = 33.8
        data["bins"][1]["min_flux"] = 28.0
    elif name == "hot_horn_blocks_focus_repetition":
        data["max_horn_temp_k"] = 309.0
        data["bins"][0]["min_flux"] = 24.0
    elif name == "delta_limit_requires_bridge_profile":
        data["max_current_delta_ka"] = 20.0
        data["bins"][2]["min_flux"] = 16.5
    elif name == "high_bin_pressure_selects_hard":
        data["max_window_heat_mj"] = 74.0
        data["bins"][2]["min_flux"] = 20.0
        data["max_shield_dose"] = 40.0
    elif name == "impossible_flux_reports_blocked":
        data["bins"][2]["min_flux"] = 80.0
    elif name == "tight_current_limit_screens_hard_profile":
        for horn in data["horns"]:
            if horn["id"] == "H3":
                horn["current_limit_ka"] = 170.0
        data["bins"][2]["min_flux"] = 15.0
    elif name == "idle_bridge_needed_for_current_delta":
        data["spill_count"] = 6
        data["max_current_delta_ka"] = 14.0
        data["bins"][0]["min_flux"] = 20.0
        data["bins"][1]["min_flux"] = 20.0
        data["bins"][2]["min_flux"] = 12.0
    elif name == "cooling_capacity_changes_peak_temperature_tie":
        for horn in data["horns"]:
            if horn["id"] == "H1":
                horn["thermal_capacity_mj_per_k"] = 5.8
                horn["cool_rate_k"] = 1.1
        data["max_horn_temp_k"] = 314.0
        data["max_shield_dose"] = 42.0
    elif name == "proton_scale_changes_screening_and_dose":
        data["protons_per_spill"] = 1.28
        data["max_window_heat_mj"] = 72.5
        data["max_shield_dose"] = 39.0
        data["bins"][0]["min_flux"] = 30.0
    elif name == "reordered_input_keeps_sorted_reports":
        data["profiles"] = list(reversed(data["profiles"]))
        data["horns"] = list(reversed(data["horns"]))
        data["bins"] = [data["bins"][2], data["bins"][0], data["bins"][1]]
    elif name == "all_profiles_screen_blocked_by_current":
        for horn in data["horns"]:
            horn["current_limit_ka"] = 1.0
        data["max_window_heat_mj"] = 1.0
    elif name == "extra_soft_profile_creates_overfill_tradeoff":
        data["profiles"].append(
            {
                "id": "soft",
                "currents_ka": {"H1": 145.0, "H2": 132.0, "H3": 94.0},
                "flux": {"low": 6.4, "mid": 3.1, "high": 1.2},
                "heat_mj": {"H1": 13.0, "H2": 10.0, "H3": 7.5},
                "shield_dose": 3.6,
            }
        )
        data["bins"][0]["min_flux"] = 29.0
        data["max_shield_dose"] = 35.0
    elif name == "shield_pressure_prefers_lower_flux_sequence":
        data["max_shield_dose"] = 31.5
        data["spill_count"] = 6
        data["bins"][0]["min_flux"] = 22.0
        data["bins"][1]["min_flux"] = 23.0
        data["bins"][2]["min_flux"] = 11.0
    elif name == "window_heat_blocks_trim_but_not_focus":
        for profile in data["profiles"]:
            if profile["id"] == "trim":
                profile["heat_mj"]["H2"] = 38.0
        data["max_window_heat_mj"] = 61.5
        data["bins"][1]["min_flux"] = 27.0
    elif name == "horn_order_and_missing_profile_keys_are_stable":
        for profile in data["profiles"]:
            if profile["id"] == "idle":
                profile["heat_mj"] = {}
                profile["flux"] = {}
                profile["currents_ka"] = {}
        data["horns"] = [data["horns"][1], data["horns"][2], data["horns"][0]]
    else:
        raise KeyError(name)
    data["case_id"] = name
    return data


class TestInputAndArtifact:
    def test_public_input_hash(self):
        assert sha(INPUT) == INPUT_HASH

    def test_source_and_command_exist(self):
        assert SOURCE.exists()
        assert BIN.exists()
        assert os.access(BIN, os.X_OK)

    def test_command_processes_a_variant_independently(self):
        """The installed command must perform the same calculation as main.js."""
        data = variant(load_case(), "dose_cap_forces_wide_trim_mix")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "beamline_case.json"
            out = root / "output"
            write_case(inp, data)
            subprocess.run([str(BIN), str(inp), str(out)], cwd="/tmp", check=True, timeout=30)
            actual = {name: json.loads((out / name).read_text(encoding="utf-8")) for name in OUT_FILES}
            assert actual == reference(data)

    def test_runtime_restrictions(self):
        text = SOURCE.read_text(encoding="utf-8")
        forbidden = ["child_process", "http.request", "https.request", "/tests", "/solution", "/logs/verifier"]
        assert not any(token in text for token in forbidden)

    def test_default_run_regenerates_outputs_and_keeps_input(self):
        before = sha(INPUT)
        run_calculation()
        assert sha(INPUT) == before


def test_public_case_matches_reference():
    data = load_case()
    out = assert_match(data)
    assert out["beam_plan.json"]["status"] == "ok"
    assert len(out["beam_plan.json"]["assignments"]) == data["spill_count"]


def test_public_case_exercises_global_constraints():
    out = assert_match(load_case())
    profiles = [row["profile_id"] for row in out["beam_plan.json"]["assignments"]]
    assert len(set(profiles)) >= 2
    assert out["thermal_trace.json"]["shield_dose"] <= load_case()["max_shield_dose"]
    assert any(row["profile_id"] == "focus" for row in out["beam_plan.json"]["assignments"])


@pytest.mark.parametrize(
    "name",
    [
        "dose_cap_forces_wide_trim_mix",
        "hot_horn_blocks_focus_repetition",
        "delta_limit_requires_bridge_profile",
        "high_bin_pressure_selects_hard",
        "impossible_flux_reports_blocked",
        "tight_current_limit_screens_hard_profile",
        "idle_bridge_needed_for_current_delta",
        "cooling_capacity_changes_peak_temperature_tie",
        "proton_scale_changes_screening_and_dose",
        "reordered_input_keeps_sorted_reports",
        "all_profiles_screen_blocked_by_current",
        "extra_soft_profile_creates_overfill_tradeoff",
        "shield_pressure_prefers_lower_flux_sequence",
        "window_heat_blocks_trim_but_not_focus",
        "horn_order_and_missing_profile_keys_are_stable",
    ],
)
def test_generated_variants_match_reference(name):
    data = variant(load_case(), name)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        inp = root / "beamline_case.json"
        out = root / "output"
        write_case(inp, data)
        assert_match(data, inp, out)


def test_empty_arrays_not_null_when_blocked():
    data = load_case()
    data["max_shield_dose"] = 1.0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        inp = root / "beamline_case.json"
        out = root / "output"
        write_case(inp, data)
        result = assert_match(data, inp, out)
        assert result["beam_plan.json"]["assignments"] == []
        assert result["thermal_trace.json"]["slots"] == []


def test_perturbing_visible_input_changes_plan():
    base = load_case()
    changed = copy.deepcopy(base)
    changed["bins"][0]["min_flux"] += 3.0
    assert reference(base)["beam_plan.json"] != reference(changed)["beam_plan.json"]
