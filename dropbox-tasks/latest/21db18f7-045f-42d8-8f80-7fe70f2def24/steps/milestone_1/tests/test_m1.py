"""Milestone 1 tests: Historical flaky-test aggregation correctness."""

import json
import os
import subprocess

import pytest
from reference_flaky import expected_report, scan_submitted_code_for_verifier_reads

REPORT_PATH = "/app/logs/report.json"


@pytest.fixture(scope="module")
def report():
    result = subprocess.run(
        ["node", "cli.js", "report"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI report command failed:\n{result.stderr}"
    assert os.path.exists(REPORT_PATH), "report.json was not written to /app/logs/"
    with open(REPORT_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def reference():
    return expected_report()


def test_report_file_exists(report):
    assert os.path.exists(REPORT_PATH)


def test_report_has_required_keys(report):
    for key in ("top_flaky", "by_browser", "total_flaky_combos"):
        assert key in report, f"report.json missing key: {key}"


def test_total_flaky_combos_correct(report, reference):
    assert report["total_flaky_combos"] == reference["total_flaky_combos"]


def test_top_flaky_entry_is_checkout_chromium(report, reference):
    assert report["top_flaky"][0] == reference["top_flaky"][0]


def test_top_flaky_sorted_by_fail_count_descending(report):
    top_flaky = report["top_flaky"]
    for i in range(len(top_flaky) - 1):
        assert top_flaky[i]["fail_count"] >= top_flaky[i + 1]["fail_count"]


def test_top_flaky_tiebreak_by_spec_file_ascending(report):
    top_flaky = report["top_flaky"]
    for i in range(len(top_flaky) - 1):
        if top_flaky[i]["fail_count"] == top_flaky[i + 1]["fail_count"]:
            assert top_flaky[i]["spec_file"] <= top_flaky[i + 1]["spec_file"]


def test_top_flaky_fail_count_is_accurate(report, reference):
    top = report["top_flaky"][0]
    expected_top = reference["top_flaky"][0]
    assert top["fail_count"] == expected_top["fail_count"]
    assert top["total_runs"] == expected_top["total_runs"]


def test_no_non_flaky_entries_in_top_flaky(report):
    for entry in report["top_flaky"]:
        assert entry["fail_count"] > 0
        assert entry["total_runs"] > entry["fail_count"]


def test_by_browser_contains_expected_browsers(report, reference):
    for browser, expected_entries in reference["by_browser"].items():
        actual_entries = report["by_browser"][browser]
        assert len(actual_entries) == len(expected_entries)
        assert {e["spec_file"] for e in actual_entries} == {
            e["spec_file"] for e in expected_entries
        }
        for actual, expected in zip(
            sorted(actual_entries, key=lambda row: row["spec_file"]),
            sorted(expected_entries, key=lambda row: row["spec_file"]),
        ):
            assert actual["fail_count"] == expected["fail_count"]
            assert actual["total_runs"] == expected["total_runs"]
            assert "browser" not in actual


def test_z_submitted_code_does_not_read_verifier_paths():
    hits = scan_submitted_code_for_verifier_reads()
    assert hits == [], (
        "Submitted application code must not read verifier paths: " + "; ".join(hits)
    )
