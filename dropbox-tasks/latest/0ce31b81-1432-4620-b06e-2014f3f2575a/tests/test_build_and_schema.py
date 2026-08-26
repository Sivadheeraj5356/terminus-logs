import json
import os
import subprocess

import reference

APP = "/app"
BINARY = os.path.join(APP, "build", "chess960_perft")
DEFAULT_POSITION = os.path.join(APP, "data", "position.txt")
DEFAULT_OUTPUT = os.path.join(APP, "output.json")


def test_binary_builds_from_source(built_binary):
    """Verify the agent's C++ source builds into an executable binary."""
    assert os.path.exists(built_binary)
    assert os.access(built_binary, os.X_OK)


def test_default_paths_are_honored_when_env_unset(built_binary):
    """Verify the binary falls back to default position/output paths when env vars are unset."""
    if os.path.exists(DEFAULT_OUTPUT):
        os.remove(DEFAULT_OUTPUT)
    env = dict(os.environ)
    env.pop("POSITION_PATH", None)
    env.pop("OUTPUT_PATH", None)
    result = subprocess.run(
        [built_binary], cwd=APP, capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, "default run failed:\n" + result.stderr
    assert os.path.exists(DEFAULT_OUTPUT), "default output path was not written"
    with open(DEFAULT_OUTPUT) as handle:
        payload = json.load(handle)
    fen, depth = reference.read_position_file(DEFAULT_POSITION)
    assert payload["perft_nodes"] == reference.perft_from_fen(fen, depth, buggy=False)


def test_output_is_a_json_object(run_engine):
    """Verify the engine's output file parses as a JSON object."""
    payload = run_engine(DEFAULT_POSITION)
    assert isinstance(payload, dict)


def test_output_has_required_field(run_engine):
    """Verify the output JSON has a perft_nodes integer field."""
    payload = run_engine(DEFAULT_POSITION)
    assert "perft_nodes" in payload
    assert isinstance(payload["perft_nodes"], int)
    assert not isinstance(payload["perft_nodes"], bool)


def test_perft_nodes_is_nonnegative(run_engine):
    """Verify perft_nodes is never negative."""
    payload = run_engine(DEFAULT_POSITION)
    assert payload["perft_nodes"] >= 0


def test_perft_nodes_is_positive_for_a_position_with_legal_moves(run_engine):
    """Verify perft_nodes is strictly positive on a position that has legal moves."""
    payload = run_engine(DEFAULT_POSITION)
    assert payload["perft_nodes"] > 0


def test_binary_also_prints_the_same_integer_to_stdout(built_binary, tmp_path):
    """Verify the binary echoes the perft count to stdout in addition to the JSON file."""
    output_path = str(tmp_path / "stdout_check_output.json")
    env = dict(os.environ)
    env["POSITION_PATH"] = DEFAULT_POSITION
    env["OUTPUT_PATH"] = output_path
    result = subprocess.run(
        [built_binary], cwd=APP, capture_output=True, text=True, env=env
    )
    assert result.returncode == 0
    with open(output_path) as handle:
        payload = json.load(handle)
    assert str(payload["perft_nodes"]) in result.stdout
