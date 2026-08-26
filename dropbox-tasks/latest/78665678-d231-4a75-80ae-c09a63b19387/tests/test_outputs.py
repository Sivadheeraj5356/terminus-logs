import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


TASK_ROOT = Path(os.environ.get("TASK_FILE_DIR", "/app/task_file"))
INPUT_DIR = TASK_ROOT / "input_data"
OUTPUT_DIR = TASK_ROOT / "output_data"
SCRIPTS_DIR = TASK_ROOT / "scripts"
BINARY = TASK_ROOT / "opt"
OUTPUT_FILE = OUTPUT_DIR / "batches.json"
SCORE_THRESHOLD = 0.91
STRICT_THRESHOLD = 0.92
INPUT_SHA256 = {'config.txt': '5b6135a8febacf969b9ab127590b469d73308ca1c85e5dac04ef4613a681c4e3', 'panels.tsv': '40cadf70265c5b482aac9d11a7e78e9106ef97bc3790f376c01d5c4cd7680469', 'samples.tsv': '92b1f281a068bb724eaf94e49a8d904ea62c6eb338916ed15a040637d59acbc1'}
MODEL_PY_SHA256 = "74a416627d50438b2f10a38f4a8572b8f54f1373b10be2161b74806900dbfc05"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, "/tests")

from model import evaluate  # noqa: E402
from model_for_tests import evaluate as strict_evaluate  # noqa: E402


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _config(path):
    return dict(line.split("=", 1) for line in Path(path).read_text().splitlines() if line.strip())


def _copy_inputs(dst):
    shutil.copytree(INPUT_DIR, dst)


class TestInputIntegrity:
    """The shipped public inputs and public scorer must remain stable."""

    def test_input_files_are_unchanged(self):
        for rel, expected in INPUT_SHA256.items():
            assert _sha(INPUT_DIR / rel) == expected

    def test_model_py_is_unchanged(self):
        assert _sha(SCRIPTS_DIR / "model.py") == MODEL_PY_SHA256


class TestOutputContract:
    """The optimizer must write the required JSON panel structure."""

    def test_output_file_exists_and_has_schema(self):
        assert OUTPUT_FILE.exists(), f"missing {OUTPUT_FILE}"
        payload = json.loads(OUTPUT_FILE.read_text())
        assert set(payload) == {"panels", "runs"}
        assert isinstance(payload["panels"], list)
        for entry in payload["panels"]:
            assert set(entry) == {"panel_id", "sample_ids"}
            assert isinstance(entry["panel_id"], str)
            assert isinstance(entry["sample_ids"], list)
            assert all(isinstance(sample_id, str) for sample_id in entry["sample_ids"])
        assert isinstance(payload["runs"], list)
        for entry in payload["runs"]:
            assert set(entry) == {"lane", "panel_ids"}
            assert isinstance(entry["lane"], str)
            assert isinstance(entry["panel_ids"], list)
            assert all(isinstance(panel_id, str) for panel_id in entry["panel_ids"])


class TestScoringAndHardConstraints:
    """The plan must satisfy hard lab constraints and clear public plus strict gates."""

    def test_public_score_clears_threshold(self):
        result = evaluate(INPUT_DIR, OUTPUT_DIR)
        assert result.get("hard_failures") == [], result
        assert result["total_score"] >= SCORE_THRESHOLD, result

    def test_strict_score_clears_threshold(self):
        result = strict_evaluate(INPUT_DIR, OUTPUT_DIR)
        assert result.get("hard_failures") == [], result
        assert result["total_score_strict"] >= STRICT_THRESHOLD, result

    def test_strict_component_triggers_are_satisfied(self):
        result = evaluate(INPUT_DIR, OUTPUT_DIR)
        assert result["reagent_score"] >= 0.80, result
        assert result["coverage_score"] >= 0.72, result
        assert result["stewardship_score"] >= 0.70, result
        assert result["sentinel_score"] == 1.0, result
        assert result["setup_score"] == 1.0, result
        assert result["total_setup"] <= 14, result
        assert result["linked_pair_count"] >= result["linked_pair_floor"] >= 6, result
        assert result["lane_target_count"] >= 4, result


class TestPanelSemantics:
    """Assignments must respect family eligibility, capacities, and sample uniqueness."""

    def test_samples_are_unique_and_known(self):
        samples = {row["sample_id"] for row in _rows(INPUT_DIR / "samples.tsv")}
        payload = json.loads(OUTPUT_FILE.read_text())
        assigned = [sample_id for entry in payload["panels"] for sample_id in entry["sample_ids"]]
        assert len(assigned) == len(set(assigned))
        assert set(assigned) <= samples

    def test_required_config_families_are_covered(self):
        cfg = _config(INPUT_DIR / "config.txt")
        samples = {row["sample_id"]: row for row in _rows(INPUT_DIR / "samples.tsv")}
        payload = json.loads(OUTPUT_FILE.read_text())
        covered = {samples[sample_id]["family"] for entry in payload["panels"] for sample_id in entry["sample_ids"]}
        assert set(cfg["families"].split("|")) <= covered

    def test_forbidden_pairs_and_cohort_separation_hold(self):
        cfg = _config(INPUT_DIR / "config.txt")
        samples = {row["sample_id"]: row for row in _rows(INPUT_DIR / "samples.tsv")}
        forbidden = [tuple(pair.split(":", 1)) for pair in cfg.get("forbidden_pairs", "").split("|") if pair]
        linked = [tuple(pair.split(":", 1)) for pair in cfg.get("linked_pairs", "").split("|") if pair]
        payload = json.loads(OUTPUT_FILE.read_text())
        sample_panel = {}
        for entry in payload["panels"]:
            assigned = set(entry["sample_ids"])
            for sample_id in assigned:
                sample_panel[sample_id] = entry["panel_id"]
            for left, right in forbidden:
                assert not ({left, right} <= assigned), (entry["panel_id"], left, right)
            cohorts = [samples[sample_id]["cohort"] for sample_id in assigned]
            assert len(cohorts) == len(set(cohorts))
        linked_complete = 0
        for left, right in linked:
            left_panel = sample_panel.get(left)
            right_panel = sample_panel.get(right)
            assert left_panel is None and right_panel is None or left_panel == right_panel
            linked_complete += int(left_panel is not None and left_panel == right_panel)
        assert linked_complete >= int(cfg.get("linked_pair_floor", "0"))

    def test_lane_schedule_uses_each_nonempty_panel_once(self):
        cfg = _config(INPUT_DIR / "config.txt")
        panels = {row["panel_id"]: row for row in _rows(INPUT_DIR / "panels.tsv")}
        payload = json.loads(OUTPUT_FILE.read_text())
        nonempty = {entry["panel_id"] for entry in payload["panels"] if entry["sample_ids"]}
        scheduled = [panel_id for entry in payload["runs"] for panel_id in entry["panel_ids"]]
        assert set(scheduled) == nonempty
        assert len(scheduled) == len(set(scheduled))
        assert len([entry for entry in payload["runs"] if entry["panel_ids"]]) == int(cfg["lane_count"])
        assert all(panel_id in panels for panel_id in scheduled)

    def test_sequence_dependent_setup_budget_holds(self):
        cfg = _config(INPUT_DIR / "config.txt")
        panels = {row["panel_id"]: row for row in _rows(INPUT_DIR / "panels.tsv")}
        setup = {}
        for item in cfg["setup_costs"].split("|"):
            left, right, cost = item.split(":")
            setup[(left, right)] = int(cost)
        payload = json.loads(OUTPUT_FILE.read_text())
        total = 0
        for entry in payload["runs"]:
            lane_total = 0
            ids = entry["panel_ids"]
            if ids:
                assert int(cfg["min_lane_panels"]) <= len(ids) <= int(cfg["max_lane_panels"])
            for left, right in zip(ids, ids[1:]):
                lane_total += setup[(panels[left]["class"], panels[right]["class"])]
            assert lane_total <= int(cfg["lane_setup_cap"])
            total += lane_total
        assert total <= int(cfg["total_setup_cap"])

    def test_lane_targets_are_met_by_scheduled_assignments(self):
        cfg = _config(INPUT_DIR / "config.txt")
        samples = {row["sample_id"]: row for row in _rows(INPUT_DIR / "samples.tsv")}
        payload = json.loads(OUTPUT_FILE.read_text())
        by_panel = {entry["panel_id"]: entry["sample_ids"] for entry in payload["panels"]}
        for item in cfg["lane_targets"].split("|"):
            lane, family = item.split(":")
            scheduled = next(entry["panel_ids"] for entry in payload["runs"] if entry["lane"] == lane)
            lane_families = {
                samples[sample_id]["family"]
                for panel_id in scheduled
                for sample_id in by_panel.get(panel_id, [])
            }
            assert family in lane_families, (lane, family, lane_families)


class TestCompiledCArtifact:
    """The answer must come from a native C executable that can regenerate the plan."""

    def test_native_binary_exists(self):
        assert BINARY.exists(), "missing /app/task_file/opt"
        assert os.access(BINARY, os.X_OK), "opt is not executable"
        assert BINARY.read_bytes()[:4] == b"\x7fELF"

    def test_binary_regenerates_after_output_delete(self):
        if OUTPUT_FILE.exists():
            OUTPUT_FILE.unlink()
        cmd = [str(BINARY)]
        if str(TASK_ROOT) != "/app/task_file":
            cmd.extend([str(INPUT_DIR), str(OUTPUT_DIR)])
        subprocess.run(cmd, cwd=TASK_ROOT, check=True, timeout=30)
        result = strict_evaluate(INPUT_DIR, OUTPUT_DIR)
        assert result["total_score_strict"] >= STRICT_THRESHOLD, result


class TestRuntimeReoptimization:
    """Mutated copied inputs are changed to require a freshly computed feasible plan."""

    def test_solver_adapts_to_tighter_public_panel_and_new_pair(self, tmp_path):
        temp_input = tmp_path / "input_data"
        temp_output = tmp_path / "output_data"
        _copy_inputs(temp_input)
        temp_output.mkdir()

        rows = (temp_input / "panels.tsv").read_text().splitlines()
        rows = [
            row.replace("A\talpha|beta|eta\t8\t8\t3\tpublic", "A\talpha|beta|eta\t8\t7\t2\tpublic")
            for row in rows
        ]
        (temp_input / "panels.tsv").write_text("\n".join(rows) + "\n")
        cfg = _config(temp_input / "config.txt")
        cfg["forbidden_pairs"] = cfg["forbidden_pairs"] + "|P02:P17"
        cfg["linked_pair_floor"] = "6"
        cfg["lane_setup_cap"] = "5"
        cfg["total_setup_cap"] = "18"
        cfg["setup_target"] = "16"
        (temp_input / "config.txt").write_text("\n".join(f"{k}={v}" for k, v in cfg.items()) + "\n")

        subprocess.run([str(BINARY), str(temp_input), str(temp_output)], cwd=TASK_ROOT, check=True, timeout=60)
        result = strict_evaluate(temp_input, temp_output)
        assert result["total_score_strict"] >= STRICT_THRESHOLD, result
        assert result["sentinel_score"] == 1.0, result
        assert result["setup_score"] == 1.0, result
        assert result["coverage_score"] >= 0.72, result

    def test_solver_handles_added_required_family_panel_and_sample(self, tmp_path):
        temp_input = tmp_path / "input_data"
        temp_output = tmp_path / "output_data"
        _copy_inputs(temp_input)
        temp_output.mkdir()

        cfg = _config(temp_input / "config.txt")
        cfg["families"] = cfg["families"] + "|nu"
        cfg["sentinel_families"] = cfg["sentinel_families"] + "|nu"
        cfg["min_sentinel_panels"] = "7"
        cfg["linked_pairs"] = cfg["linked_pairs"] + "|P29:P30"
        cfg["linked_pair_floor"] = "7"
        cfg["risk_floor"] = "198"
        cfg["risk_target"] = "232"
        cfg["total_setup_cap"] = "22"
        cfg["setup_target"] = "20"
        (temp_input / "config.txt").write_text("\n".join(f"{k}={v}" for k, v in cfg.items()) + "\n")
        with open(temp_input / "panels.tsv", "a", encoding="utf-8") as fh:
            fh.write("M\tnu|theta|lambda\t8\t8\t3\tconfirm\n")
        with open(temp_input / "samples.tsv", "a", encoding="utf-8") as fh:
            fh.write("P29\tnu\t14\t3\t2\t1\tc29\n")
            fh.write("P30\tnu\t6\t2\t2\t0\tc30\n")

        subprocess.run([str(BINARY), str(temp_input), str(temp_output)], cwd=TASK_ROOT, check=True, timeout=60)
        payload = json.loads((temp_output / "batches.json").read_text())
        by_panel = {entry["panel_id"]: set(entry["sample_ids"]) for entry in payload["panels"]}
        result = strict_evaluate(temp_input, temp_output)
        assert result["total_score_strict"] >= STRICT_THRESHOLD, result
        assert "P29" in by_panel.get("M", set())
        assert result["sentinel_score"] == 1.0
        assert result["setup_score"] == 1.0, result

    def test_solver_handles_setup_budget_and_linked_block_shift(self, tmp_path):
        temp_input = tmp_path / "input_data"
        temp_output = tmp_path / "output_data"
        _copy_inputs(temp_input)
        temp_output.mkdir()

        cfg = _config(temp_input / "config.txt")
        cfg["linked_pairs"] = cfg["linked_pairs"] + "|P04:P18"
        cfg["linked_pair_floor"] = "7"
        cfg["risk_floor"] = "194"
        cfg["risk_target"] = "226"
        cfg["forbidden_pairs"] = cfg["forbidden_pairs"] + "|P08:P09"
        cfg["lane_setup_cap"] = "5"
        cfg["total_setup_cap"] = "18"
        cfg["setup_target"] = "16"
        (temp_input / "config.txt").write_text("\n".join(f"{k}={v}" for k, v in cfg.items()) + "\n")

        subprocess.run([str(BINARY), str(temp_input), str(temp_output)], cwd=TASK_ROOT, check=True, timeout=60)
        result = strict_evaluate(temp_input, temp_output)
        assert result["total_score_strict"] >= STRICT_THRESHOLD, result
        assert result["linked_pair_count"] >= 7, result
        assert result["total_setup"] <= 18, result
        assert result["setup_score"] == 1.0, result
