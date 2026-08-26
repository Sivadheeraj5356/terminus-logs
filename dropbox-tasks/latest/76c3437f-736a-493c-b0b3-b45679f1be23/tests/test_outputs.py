"""Behavioral verifier for the safari species census profiles."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from common_safari_species_counting import (
    CASE_ROWS,
    REPORT_ROWS,
    app_dir,
    assert_completion,
    assert_protected_hashes,
    dispatcher_environment,
    dispatcher_path,
    play_case,
    render_report,
)


MIN_SCORE = 17800


@dataclass(frozen=True)
class HiddenCase:
    """Seeded verifier case with a seed-free representation for failure output."""

    scenario_id: str
    seed: int
    label: str

    def __repr__(self) -> str:
        return self.label


HIDDEN_CASES = [HiddenCase(scenario_id, seed, case_label) for scenario_id, seed, case_label in CASE_ROWS]
SEED_TO_CASE = {case.seed: case for case in HIDDEN_CASES}
SEEDS = list(SEED_TO_CASE)
SCORED_SEEDS = list(SEEDS)
LEVEL_BARS = {1: MIN_SCORE}
CASES = [(1, seed, MIN_SCORE) for seed in SEEDS]
PYTEST_CASES = [(case, MIN_SCORE) for case in HIDDEN_CASES]


def run_seed(level: int, seed: int, threshold: int = MIN_SCORE) -> dict[str, object]:
    """Run one scored census for solver and threshold calibration."""
    assert level == 1
    case = SEED_TO_CASE[seed]
    state = play_case(case.scenario_id, seed, case.label)
    assert_completion(state, threshold)
    return {"score": state["score"], "scenario": case.scenario_id, "case": case.label}


@pytest.fixture(scope="module", autouse=True)
def census_report() -> None:
    """Print the seed-safe census summary after all cases finish."""
    yield
    print("\ncensus_summary")
    print(render_report(REPORT_ROWS))


class TestOutputs:
    """Safari runtime integrity and scored behavior checks."""

    def test_runtime_files_exist(self) -> None:
        """The packaged runtime and editable dispatcher must exist."""
        assert app_dir().exists()
        assert dispatcher_path().exists()

    def test_protected_runtime_is_unchanged(self) -> None:
        """Protected runtime content must retain its packaged hashes."""
        assert_protected_hashes()

    def test_dispatcher_environment_hides_verifier_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Submitted code must not inherit verifier paths, secrets, or pytest case identifiers."""
        monkeypatch.setenv("TEST_DIR", "/tests")
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_outputs.py::TestOutputs::test_census_case[case_01] (call)")
        monkeypatch.setenv("TASK_VERIFIER_HMAC_KEY_FILE", "/tmp/secret")
        monkeypatch.setenv("TASK_EXPECTED_HASHES_PATH", "/tests/expected_hashes.json")
        environment = dispatcher_environment()
        assert "TEST_DIR" not in environment
        assert "PYTEST_CURRENT_TEST" not in environment
        assert not any(name.startswith("TASK_") for name in environment)

    def test_dispatcher_parses(self) -> None:
        """The editable dispatcher must parse under the packaged Node runtime."""
        result = subprocess.run(
            ["node", "--check", str(dispatcher_path())],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    @pytest.mark.parametrize(
        ("case", "threshold"),
        PYTEST_CASES,
        ids=[case.label for case in HIDDEN_CASES],
    )
    def test_census_case(self, case: HiddenCase, threshold: int) -> None:
        """Each hidden census must submit complete and clear the uniform score bar."""
        state = play_case(case.scenario_id, case.seed, case.label)
        assert state["scenario"]["id"] == case.scenario_id
        assert_completion(state, threshold)
