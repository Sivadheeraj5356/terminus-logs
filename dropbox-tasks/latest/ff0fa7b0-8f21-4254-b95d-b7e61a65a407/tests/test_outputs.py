"""Verifier for calibration scheduling."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from functools import lru_cache


TASK_ROOT = os.environ.get("TASK_FILE_DIR", "/app/task_file")
SCAN = os.path.join(TASK_ROOT, "scan_input")
OUTPUT = os.path.join(TASK_ROOT, "output")
REFERENCE_RS = os.path.join(os.path.dirname(__file__), "reference.rs")

INPUT_HASHES = {
    "incident_case.txt": "743d87af1067c641c7ca0112c66a0ae6070cc9d7e8f47ca57e9815642fc7c711",
}

_REFBIN = None


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def setUpModule():
    global _REFBIN
    rustc = "/root/.cargo/bin/rustc"
    if not os.path.exists(rustc):
        rustc = "rustc"
    tmp = tempfile.mkdtemp(prefix="calib_ref_")
    _REFBIN = os.path.join(tmp, "reference")
    subprocess.run(
        [rustc, "--edition", "2021", "-C", "opt-level=3", "-o", _REFBIN, REFERENCE_RS],
        check=True,
    )


def output_path() -> str:
    return os.path.join(OUTPUT, "containment_schedule.json")


@lru_cache(maxsize=1)
def parse_case() -> dict:
    params = {}
    scenarios = []
    workflows = []
    crowns = []
    evidence = []
    with open(os.path.join(SCAN, "incident_case.txt"), encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == "PARAM":
                params[parts[1]] = int(parts[2]) if parts[1] != "file_version" else parts[2]
            elif parts[0] == "SCENARIO":
                scenarios.append(parts[1])
            elif parts[0] == "WORKFLOW":
                workflows.append(parts[1])
            elif parts[0] == "CROWN":
                crowns.append(parts[1])
            elif parts[0] == "EVIDENCE":
                evidence.append(parts[1])
    return {
        "params": params,
        "scenarios": scenarios,
        "workflows": workflows,
        "crowns": crowns,
        "evidence": evidence,
    }


@lru_cache(maxsize=1)
def reference_plan() -> dict:
    raw = subprocess.check_output(
        [_REFBIN, os.path.join(SCAN, "incident_case.txt")],
        text=True,
    )
    return json.loads(raw)


def load_output() -> dict:
    with open(output_path(), encoding="utf-8") as f:
        return json.load(f)


class TestInputIntegrity(unittest.TestCase):
    def test_case_unchanged(self):
        """Verify the scanned input file was not modified."""
        for rel, expected in INPUT_HASHES.items():
            path = os.path.join(SCAN, rel)
            self.assertTrue(os.path.exists(path), f"{rel} is missing")
            self.assertEqual(sha256_file(path), expected, f"{rel} was modified")


class TestContainmentShape(unittest.TestCase):
    def test_output_exists_and_is_valid(self):
        """Verify the output file exists and has the expected JSON shape."""
        path = output_path()
        self.assertTrue(
            os.path.exists(path),
            "containment_schedule.json not found at /app/task_file/output/containment_schedule.json",
        )
        data = load_output()
        case = parse_case()
        self.assertIsInstance(data, dict)
        self.assertIsInstance(data.get("response_score_units"), int)
        self.assertIsInstance(data.get("total_disruption_points"), int)
        self.assertIsInstance(data.get("total_review_minutes"), int)
        self.assertIsInstance(data.get("preserved_evidence_points"), int)
        self.assertIsInstance(data.get("preserved_evidence_ids"), list)
        self.assertIsInstance(data.get("scenario_results"), list)
        self.assertIsInstance(data.get("waves"), list)
        self.assertEqual(len(data["scenario_results"]), len(case["scenarios"]))
        self.assertEqual(len(data["waves"]), case["params"]["wave_count"])
        for evidence_id in data["preserved_evidence_ids"]:
            self.assertIn(evidence_id, case["evidence"])

        seen_action_ids = set()
        seen_scenarios = []
        for scenario_result in data["scenario_results"]:
            self.assertIsInstance(scenario_result, dict)
            self.assertIsInstance(scenario_result.get("scenario_id"), str)
            self.assertIsInstance(scenario_result.get("protected_crown_ids"), list)
            seen_scenarios.append(scenario_result["scenario_id"])
            for crown_id in scenario_result["protected_crown_ids"]:
                self.assertIn(crown_id, case["crowns"])
        self.assertEqual(seen_scenarios, case["scenarios"])

        for expected_wave_index, wave in enumerate(data["waves"], start=1):
            self.assertIsInstance(wave, dict)
            self.assertEqual(wave.get("wave_index"), expected_wave_index)
            self.assertIsInstance(wave.get("action_ids"), list)
            self.assertIsInstance(wave.get("broken_workflow_ids"), list)
            self.assertIsInstance(wave.get("actions"), list)
            self.assertLessEqual(len(wave["action_ids"]), case["params"]["max_actions_per_wave"])
            self.assertEqual(wave["action_ids"], sorted(wave["action_ids"]))
            self.assertEqual(len(wave["action_ids"]), len(wave["actions"]))
            for workflow_id in wave["broken_workflow_ids"]:
                self.assertIn(workflow_id, case["workflows"])
            for action in wave["actions"]:
                self.assertIsInstance(action, dict)
                self.assertIsInstance(action.get("action_id"), str)
                self.assertIsInstance(action.get("action_type"), str)
                self.assertIsInstance(action.get("target_id"), str)
                self.assertIsInstance(action.get("owner"), str)
                self.assertIsInstance(action.get("disruption_points"), int)
                self.assertIsInstance(action.get("approval_ids"), list)
                self.assertIsInstance(action.get("captured_evidence_ids"), list)
                self.assertIsInstance(action.get("cleared_node_ids"), list)
                self.assertIsInstance(action.get("blocked_edge_ids"), list)
                self.assertNotIn(action["action_id"], seen_action_ids)
                seen_action_ids.add(action["action_id"])
                for evidence_id in action["captured_evidence_ids"]:
                    self.assertIn(evidence_id, case["evidence"])


class TestContainmentPlan(unittest.TestCase):
    def test_containment_plan_matches_reference(self):
        """Verify the produced schedule exactly matches the reference plan."""
        self.assertEqual(load_output(), reference_plan())

    def test_containment_plan_satisfies_declared_rules(self):
        """Verify the main score and ordering fields match the reference result."""
        output = load_output()
        reference = reference_plan()
        self.assertEqual(output["response_score_units"], reference["response_score_units"])
        self.assertEqual(output["total_review_minutes"], reference["total_review_minutes"])
        self.assertEqual(
            output["preserved_evidence_points"],
            reference["preserved_evidence_points"],
        )
        self.assertEqual(
            [wave["action_ids"] for wave in output["waves"]],
            [wave["action_ids"] for wave in reference["waves"]],
        )
