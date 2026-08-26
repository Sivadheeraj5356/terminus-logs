import os

import reference

APP = "/app"
DATA = os.path.join(APP, "data")


def test_default_position_is_deterministic_across_runs(run_engine):
    """Verify running the engine twice on the default position gives the same count both times."""
    path = os.path.join(DATA, "position.txt")
    first = run_engine(path)
    second = run_engine(path)
    assert first["perft_nodes"] == second["perft_nodes"]


def test_hidden_combined_seed_is_deterministic_across_runs(run_engine):
    """Verify running the engine twice on the combined hidden trap case gives the same count both times."""
    path = reference.hidden_case_path("hidden_combined_seed")
    first = run_engine(path)
    second = run_engine(path)
    assert first["perft_nodes"] == second["perft_nodes"]


def test_control_case_is_deterministic_and_correct_both_times(run_engine):
    """Verify the control case is deterministic across runs and matches the reference both times."""
    path = reference.hidden_case_path("hidden_control_no_trap")
    fen, depth = reference.read_position_file(path)
    expected = reference.perft_from_fen(fen, depth, buggy=False)
    first = run_engine(path)
    second = run_engine(path)
    assert first["perft_nodes"] == expected
    assert second["perft_nodes"] == expected
