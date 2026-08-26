import json
import os
import subprocess
from pathlib import Path

import pytest

APP_ROOT = Path(os.environ.get("CONANPLAN_APP_ROOT", "/app"))
TOOL = Path(os.environ.get("CONANPLAN_BIN", str(APP_ROOT / "bin" / "conanplan")))
ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
INPUT_FILES = (
    "profile-requests.json",
    "recipe-index.json",
    "conan-lock.json",
    "package-cache.json",
)


def load_json(path: Path):
    return json.loads(path.read_text())


def run_tool(input_dir: Path, output_path: Path):
    assert TOOL.exists(), f"{TOOL} does not exist"
    assert os.access(TOOL, os.X_OK), f"{TOOL} is not executable"
    proc = subprocess.run(
        [str(TOOL), str(input_dir), str(output_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert output_path.exists(), "planner did not write the requested output path"
    return load_json(output_path)


def case_dir(name: str) -> Path:
    return FIXTURES / name


def case_input(name: str) -> Path:
    return case_dir(name) / "input"


def case_expected(name: str):
    return load_json(case_dir(name) / "expected.json")


@pytest.mark.parametrize(
    ("name", "expected_summary"),
    [
        ("public", {"selected": 6, "reused": 3, "built": 3, "conflicts": 0}),
        ("audit-release", {"selected": 7, "reused": 2, "built": 5, "conflicts": 1}),
        ("conflict-late-pin", {"selected": 6, "reused": 3, "built": 3, "conflicts": 1}),
        ("locked-defaults", {"selected": 6, "reused": 3, "built": 3, "conflicts": 0}),
    ],
)
def test_fixture_cases_match_expected(tmp_path, name, expected_summary):
    got = run_tool(case_input(name), tmp_path / f"{name}.json")
    expected = case_expected(name)
    assert got == expected
    assert got["summary"] == expected_summary


def test_public_input_matches_expected_and_is_unchanged(tmp_path):
    input_dir = APP_ROOT / "input"
    before = {name: (input_dir / name).read_bytes() for name in INPUT_FILES}
    got = run_tool(input_dir, tmp_path / "plan.json")
    assert got == case_expected("public")
    after = {name: (input_dir / name).read_bytes() for name in INPUT_FILES}
    assert after == before


def test_locked_defaults_are_active_before_any_stage(tmp_path):
    got = run_tool(case_input("locked-defaults"), tmp_path / "locked-defaults.json")
    docsgen = next(entry for entry in got["final_lock"] if entry["name"] == "docsgen")
    assert docsgen["features"] == ["base"]


def test_cli_requires_exactly_two_positional_arguments():
    proc = subprocess.run(
        [str(TOOL)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 2
