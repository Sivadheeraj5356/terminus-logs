"""Milestone 2 tests: Playwright plan generation correctness."""

import json
import os
import subprocess

import pytest
from reference_flaky import expected_plan, scan_submitted_code_for_verifier_reads

PLAN_PATH = "/app/logs/plan.json"


@pytest.fixture(scope="module")
def plan():
    result = subprocess.run(
        ["node", "cli.js", "plan", "--session", "plan-sess-alpha"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI plan command failed:\n{result.stderr}"
    assert os.path.exists(PLAN_PATH), "plan.json was not written to /app/logs/"
    with open(PLAN_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def reference():
    return expected_plan()


def test_plan_file_exists(plan):
    assert os.path.exists(PLAN_PATH)


def test_plan_has_required_keys(plan, reference):
    assert plan["session_id"] == reference["session_id"]
    assert "projects" in plan
    assert plan["total_specs"] == reference["total_specs"]


def test_plan_has_three_projects(plan, reference):
    assert len(plan["projects"]) == len(reference["projects"])


def test_chromium_project_uses_correct_name(plan, reference):
    expected = next(p for p in reference["projects"] if p["browser"] == "chromium")
    actual = next(p for p in plan["projects"] if p["browser"] == "chromium")
    assert actual["name"] == expected["name"]


def test_chromium_retries_from_db(plan, reference):
    expected = next(p for p in reference["projects"] if p["browser"] == "chromium")
    actual = next(p for p in plan["projects"] if p["browser"] == "chromium")
    assert actual["retries"] == expected["retries"]


def test_firefox_retries_from_db(plan, reference):
    expected = next(p for p in reference["projects"] if p["browser"] == "firefox")
    actual = next(p for p in plan["projects"] if p["browser"] == "firefox")
    assert actual["retries"] == expected["retries"]


def test_chromium_worker_count_correct(plan, reference):
    expected = next(p for p in reference["projects"] if p["browser"] == "chromium")
    actual = next(p for p in plan["projects"] if p["browser"] == "chromium")
    assert actual["workers"] == expected["workers"]


def test_chromium_shards_from_db(plan, reference):
    expected = next(p for p in reference["projects"] if p["browser"] == "chromium")
    actual = next(p for p in plan["projects"] if p["browser"] == "chromium")
    assert actual["shards"] == expected["shards"]


def test_firefox_project_config_from_db(plan, reference):
    expected = next(p for p in reference["projects"] if p["browser"] == "firefox")
    actual = next(p for p in plan["projects"] if p["browser"] == "firefox")
    assert actual["workers"] == expected["workers"]
    assert actual["shards"] == expected["shards"]


def test_webkit_project_config_from_db(plan, reference):
    expected = next(p for p in reference["projects"] if p["browser"] == "webkit")
    actual = next(p for p in plan["projects"] if p["browser"] == "webkit")
    assert actual["workers"] == expected["workers"]
    assert actual["shards"] == expected["shards"]


def test_all_projects_have_testmatch(plan, reference):
    for expected_project in reference["projects"]:
        actual = next(p for p in plan["projects"] if p["browser"] == expected_project["browser"])
        assert set(actual["testMatch"]) == set(expected_project["testMatch"])
        for spec in actual["testMatch"]:
            assert spec.startswith("tests/e2e/")


def test_z_submitted_code_does_not_read_verifier_paths():
    hits = scan_submitted_code_for_verifier_reads()
    assert hits == [], (
        "Submitted application code must not read verifier paths: " + "; ".join(hits)
    )
