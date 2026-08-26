from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import statistics
import subprocess
from collections import Counter
from pathlib import Path

import pytest


BASE = Path("/app/task_file")
if not BASE.exists():
    BASE = Path(__file__).parent.parent / "environment" / "task_file"
INP = BASE / "input_data"
OUT = BASE / "output_data"
EXPECTED_HASHES = {
    "crews.jsonl": "f76326fe81e1e2e7165ceddd09c171cd56d9ac59a567818f910a22cd7ae5eeed",
    "input_hashes.json": "afc2e57550d352f8192b203bd9fe95ca53fecc4f3e17385e23847d12559dceb3",
    "precedence_edges.jsonl": "433e6e19fad6ee1d5014094721000b33422db0a217172460b2344a5a3636c60f",
    "recovery_windows.json": "aa65876ddfdc7ff247f225470e10437502a57bedd1c34e8c284246aa3115152a",
    "relief_terminals.jsonl": "038a23fca4d04b73b8bf5b6164f72ffdcc3dfffc3267bb7c32c1e0b83009b169",
    "route_targets.json": "de7d5cd97ab2711d9fd269f49fa46c6b5de0e7f0047a7f9dbe35817c8a167028",
    "sailings.jsonl": "e2ba1e87d0209e9c04da6a2893a719ddb701d7096c1d5ae065266943a89cf5fe",
    "task_config.json": "755c9049ebd7e29263c51b1eb52e01c7724d8f3b2c8b3a202d7ae2169bd1c8b8",
    "vessel_capacity.json": "002067322158ae6fd77e5b847728d9c271d423bedf1bc40a92d9b4c2a38340aa"
}
MODEL_SHA256 = "fb46f99fc63007a858aa8a32acca6a1d5ed6355031fdb26f75e174b10850d767"
RAW_THRESHOLD = 0.965
STRICT_THRESHOLD = 0.888
PERTURBED_RAW_THRESHOLD = 0.780
STRESS_RAW_THRESHOLD = 0.940
MIN_ASSIGNED = 160
MAX_ASSIGNED = 160
MIN_PROTECTED_PASSENGER_MINUTES = 3300000
STRESS_MIN_PROTECTED_PASSENGER_MINUTES = 3500000
VALID_MODES = {"RELIEF", "SWAP", "DEADHEAD", "STANDBY"}

SPEC = importlib.util.spec_from_file_location("model_for_tests", Path(__file__).parent / "model_for_tests.py")
model_for_tests = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(model_for_tests)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_go_solver(go_sources, tmp_path):
    errors = []
    for path in sorted(go_sources):
        binary = tmp_path / "ferry_solver"
        result = subprocess.run(
            ["/usr/local/go/bin/go", "build", "-o", str(binary), str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return binary
        errors.append(result.stderr[-400:])
    pytest.fail("no standalone Go package main source compiled: " + " | ".join(errors[-3:]))


def assert_valid_scored_output(input_dir, output_dir, raw_floor=RAW_THRESHOLD, strict_floor=STRICT_THRESHOLD):
    score = model_for_tests.score_strict(input_dir, output_dir)
    assert not score.get("penalty"), score
    assert not score.get("error"), score
    assert score["total_score"] >= raw_floor, score
    assert score["total_score_strict"] >= strict_floor, score
    assert score["impact_score"] >= 0.990, score
    assert score["coverage_score"] >= 1.000, score
    assert score["deadline_score"] >= 0.940, score
    assert score["crew_fit_score"] >= 0.990, score
    assert score["rest_buffer_score"] >= 0.960, score
    assert score["chain_score"] >= 1.000, score
    assert score["tide_isolation_score"] >= 0.860, score
    assert score["route_balance_score"] >= 0.930, score
    assert score["terminal_balance_score"] >= 1.000, score
    assert score["mode_shape_score"] >= 0.930, score
    assert score["cell_coverage"] >= 1.000, score
    assert score["protected_passenger_minutes"] >= MIN_PROTECTED_PASSENGER_MINUTES, score
    return score


def assert_valid_perturbed_output(input_dir, output_dir):
    score = model_for_tests.score_strict(input_dir, output_dir)
    assert not score.get("penalty"), score
    assert not score.get("error"), score
    assert score["total_score"] >= PERTURBED_RAW_THRESHOLD, score
    return score


def assert_valid_stress_output(input_dir, output_dir):
    score = model_for_tests.score_strict(input_dir, output_dir)
    assert not score.get("penalty"), score
    assert not score.get("error"), score
    assert score["total_score"] >= STRESS_RAW_THRESHOLD, score
    assert score["assigned_count"] == MIN_ASSIGNED == MAX_ASSIGNED, score
    assert score["cell_coverage"] >= 1.000, score
    assert score["protected_passenger_minutes"] >= STRESS_MIN_PROTECTED_PASSENGER_MINUTES, score
    return score


@pytest.fixture(scope="module")
def sailings():
    return {row["sailing_id"]: row for row in read_jsonl(INP / "sailings.jsonl")}


@pytest.fixture(scope="module")
def crews():
    return {row["crew_id"]: row for row in read_jsonl(INP / "crews.jsonl")}


@pytest.fixture(scope="module")
def terminals():
    return {row["relief_terminal_id"]: row for row in read_jsonl(INP / "relief_terminals.jsonl")}


@pytest.fixture(scope="module")
def plan_rows():
    return read_jsonl(OUT / "ferry_recovery_plan.jsonl")


@pytest.fixture(scope="module")
def summary():
    return json.loads((OUT / "ferry_recovery_summary.json").read_text())


@pytest.fixture(scope="module")
def score_result():
    return model_for_tests.score_strict(INP, OUT)


class TestIntegrity:
    def test_input_hashes_match(self):
        for name, want in EXPECTED_HASHES.items():
            path = INP / name
            assert path.exists(), f"missing hashed input {name}"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == want, name

    def test_public_model_not_modified(self):
        path = BASE / "scripts" / "model.py"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == MODEL_SHA256


class TestOutputContract:
    def test_required_files_exist(self):
        assert (OUT / "ferry_recovery_plan.jsonl").exists()
        assert (OUT / "ferry_recovery_summary.json").exists()

    def test_schema_and_ids(self, sailings, crews, terminals, plan_rows):
        required = {
            "sailing_id",
            "crew_id",
            "relief_terminal_id",
            "recovery_window",
            "priority_rank",
            "handoff_mode",
            "rest_buffer_minutes",
        }
        ids = []
        ranks = []
        for row in plan_rows:
            assert set(row) == required
            assert row["sailing_id"] in sailings
            assert row["crew_id"] in crews
            assert row["relief_terminal_id"] in terminals
            assert isinstance(row["recovery_window"], int) and 1 <= row["recovery_window"] <= 6
            assert isinstance(row["priority_rank"], int)
            assert row["handoff_mode"] in VALID_MODES
            assert isinstance(row["rest_buffer_minutes"], (int, float))
            assert 10 <= float(row["rest_buffer_minutes"]) <= 90
            ids.append(row["sailing_id"])
            ranks.append(row["priority_rank"])
        assert len(ids) == len(set(ids))
        assert sorted(ranks) == list(range(1, len(ranks) + 1))

    def test_summary_matches_plan(self, sailings, crews, plan_rows, summary):
        window_counts = Counter(str(row["recovery_window"]) for row in plan_rows)
        route_counts = Counter(sailings[row["sailing_id"]]["route_id"] for row in plan_rows)
        crew_counts = Counter(row["crew_id"] for row in plan_rows)
        terminal_counts = Counter(row["relief_terminal_id"] for row in plan_rows)
        protected = sum(
            float(sailings[row["sailing_id"]]["passengers"]) * float(sailings[row["sailing_id"]]["disruption_minutes"])
            for row in plan_rows
        )
        expected = {
            "assigned_count": len(plan_rows),
            "window_counts": dict(sorted(window_counts.items())),
            "route_counts": dict(sorted(route_counts.items())),
            "crew_counts": dict(sorted(crew_counts.items())),
            "terminal_counts": dict(sorted(terminal_counts.items())),
            "total_protected_passenger_minutes": round(protected, 3),
        }
        assert summary == expected


class TestScoreAndDiversity:
    def test_score_contract(self, score_result):
        assert_valid_scored_output(INP, OUT)

    def test_mandatory_sailings_and_assignment_band(self, sailings, plan_rows):
        assigned = {row["sailing_id"] for row in plan_rows}
        mandatory = {sid for sid, row in sailings.items() if row["mandatory"]}
        assert mandatory <= assigned
        assert MIN_ASSIGNED <= len(plan_rows) <= MAX_ASSIGNED

    def test_distribution_pressure(self, sailings, crews, plan_rows):
        windows = Counter(row["recovery_window"] for row in plan_rows)
        routes = Counter(sailings[row["sailing_id"]]["route_id"] for row in plan_rows)
        bases = Counter(crews[row["crew_id"]]["base_id"] for row in plan_rows)
        modes = Counter(row["handoff_mode"] for row in plan_rows)
        cells = {(row["recovery_window"], crews[row["crew_id"]]["base_id"]) for row in plan_rows}
        total = len(plan_rows)
        assert len(windows) == 6
        assert len(routes) == 6
        assert len(bases) == 4
        assert len(modes) == 4
        assert len(cells) == 24
        assert max(windows.values()) / total <= 0.22
        assert max(routes.values()) / total <= 0.24
        assert max(bases.values()) / total <= 0.32
        assert len(Counter(row["relief_terminal_id"] for row in plan_rows)) >= 6

    def test_rest_buffers_are_not_placeholders(self, plan_rows):
        rounded = [round(float(row["rest_buffer_minutes"])) for row in plan_rows]
        assert len(set(rounded)) >= 12
        assert statistics.pstdev(rounded) >= 8.5


class TestCompiledSolver:
    @pytest.fixture(scope="class")
    def go_sources(self):
        roots = [Path("/app"), Path("/tmp")]
        local_root = Path(__file__).parent.parent
        if local_root != Path("/"):
            roots.append(local_root)
        found = []
        for root in roots:
            if root.exists():
                found.extend(path for path in root.rglob("*.go") if "solution" not in path.parts)
        assert found, "submit at least one Go source file under /app or /tmp"
        return found

    def test_go_source_compiles(self, go_sources, tmp_path):
        assert build_go_solver(go_sources, tmp_path).exists()

    def test_go_binary_regenerates_original_outputs(self, go_sources, tmp_path):
        binary = build_go_solver(go_sources, tmp_path)
        fresh_out = tmp_path / "fresh_out"
        fresh_out.mkdir()
        result = subprocess.run(
            [str(binary), str(INP), str(fresh_out)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr[-500:]
        assert_valid_scored_output(INP, fresh_out)

    def test_go_binary_responds_to_perturbed_inputs(self, go_sources, tmp_path):
        binary = build_go_solver(go_sources, tmp_path)
        perturbed_in = tmp_path / "input_data"
        shutil.copytree(INP, perturbed_in)
        rows = read_jsonl(perturbed_in / "sailings.jsonl")
        for row in rows:
            if row["sailing_id"] == "FERRY-0228":
                row["mandatory"] = True
                row["passengers"] = 720
                row["disruption_minutes"] = 118
                row["priority_weight"] = 1.44
                row["earliest_window"] = 2
                row["deadline_window"] = 4
        with (perturbed_in / "sailings.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        hashes = json.loads((perturbed_in / "input_hashes.json").read_text())
        hashes["sailings.jsonl"] = hashlib.sha256((perturbed_in / "sailings.jsonl").read_bytes()).hexdigest()
        (perturbed_in / "input_hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
        perturbed_out = tmp_path / "perturbed_out"
        perturbed_out.mkdir()
        result = subprocess.run(
            [str(binary), str(perturbed_in), str(perturbed_out)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr[-500:]
        new_rows = read_jsonl(perturbed_out / "ferry_recovery_plan.jsonl")
        new_ids = {row["sailing_id"] for row in new_rows}
        assert "FERRY-0228" in new_ids
        assert_valid_perturbed_output(perturbed_in, perturbed_out)

    def test_go_binary_handles_capacity_stress_copy(self, go_sources, tmp_path):
        binary = build_go_solver(go_sources, tmp_path)
        stress_in = tmp_path / "stress_input_data"
        shutil.copytree(INP, stress_in)
        stressed_ids = {"FERRY-0189", "FERRY-0203", "FERRY-0217", "FERRY-0221"}
        rows = read_jsonl(stress_in / "sailings.jsonl")
        for row in rows:
            if row["sailing_id"] in stressed_ids:
                row["mandatory"] = True
                row["passengers"] = max(row["passengers"], 690)
                row["disruption_minutes"] = max(row["disruption_minutes"], 112)
                row["priority_weight"] = 1.43
                row["earliest_window"] = max(1, int(row["earliest_window"]) - 1)
                row["deadline_window"] = min(6, int(row["deadline_window"]) + 1)
        with (stress_in / "sailings.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        capacity = json.loads((stress_in / "vessel_capacity.json").read_text())
        for window in ("3", "4"):
            for vessel_class, value in list(capacity["by_window"][window].items()):
                capacity["by_window"][window][vessel_class] = max(8, int(value) - 2)
        (stress_in / "vessel_capacity.json").write_text(json.dumps(capacity, indent=2, sort_keys=True) + "\n")
        hashes = json.loads((stress_in / "input_hashes.json").read_text())
        for name in ("sailings.jsonl", "vessel_capacity.json"):
            hashes[name] = hashlib.sha256((stress_in / name).read_bytes()).hexdigest()
        (stress_in / "input_hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
        stress_out = tmp_path / "stress_out"
        stress_out.mkdir()
        result = subprocess.run(
            [str(binary), str(stress_in), str(stress_out)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr[-500:]
        stress_rows = read_jsonl(stress_out / "ferry_recovery_plan.jsonl")
        stress_assigned = {row["sailing_id"] for row in stress_rows}
        assert stressed_ids <= stress_assigned
        assert_valid_stress_output(stress_in, stress_out)
