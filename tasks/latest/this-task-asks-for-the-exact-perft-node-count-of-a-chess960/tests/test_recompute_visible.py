import json
import os

import reference

APP = "/app"
DATA = os.path.join(APP, "data")


def test_default_position_matches_independent_reference(run_engine):
    """Verify the default position's perft count matches the independent reference."""
    path = os.path.join(DATA, "position.txt")
    fen, depth = reference.read_position_file(path)
    payload = run_engine(path)
    assert payload["perft_nodes"] == reference.perft_from_fen(fen, depth, buggy=False)


def test_kr_vs_k_matches_committed_expected_file(run_engine):
    """Verify the king-and-rook-versus-king case matches the committed expected JSON."""
    path = os.path.join(DATA, "sanity_kr_vs_k.txt")
    with open(os.path.join(DATA, "sanity_kr_vs_k_expected.json")) as handle:
        expected = json.load(handle)
    payload = run_engine(path)
    assert payload["perft_nodes"] == expected["perft_nodes"]


def test_kr_vs_k_matches_independent_reference(run_engine):
    """Verify the king-and-rook-versus-king case matches the independent reference recomputation."""
    path = os.path.join(DATA, "sanity_kr_vs_k.txt")
    fen, depth = reference.read_position_file(path)
    payload = run_engine(path)
    assert payload["perft_nodes"] == reference.perft_from_fen(fen, depth, buggy=False)


def test_midgame_captures_matches_committed_expected_file(run_engine):
    """Verify the midgame capture case matches the committed expected JSON."""
    path = os.path.join(DATA, "sanity_midgame_captures.txt")
    with open(os.path.join(DATA, "sanity_midgame_captures_expected.json")) as handle:
        expected = json.load(handle)
    payload = run_engine(path)
    assert payload["perft_nodes"] == expected["perft_nodes"]


def test_midgame_captures_matches_independent_reference(run_engine):
    """Verify the midgame capture case matches the independent reference recomputation."""
    path = os.path.join(DATA, "sanity_midgame_captures.txt")
    fen, depth = reference.read_position_file(path)
    payload = run_engine(path)
    assert payload["perft_nodes"] == reference.perft_from_fen(fen, depth, buggy=False)


def test_standard_start_d3_matches_committed_expected_file(run_engine):
    """Verify the standard-arrangement depth-three case matches the committed expected JSON."""
    path = os.path.join(DATA, "sanity_standard_start_d3.txt")
    with open(os.path.join(DATA, "sanity_standard_start_d3_expected.json")) as handle:
        expected = json.load(handle)
    payload = run_engine(path)
    assert payload["perft_nodes"] == expected["perft_nodes"]


def test_standard_start_d3_matches_independent_reference(run_engine):
    """Verify the standard-arrangement depth-three case matches the independent reference recomputation."""
    path = os.path.join(DATA, "sanity_standard_start_d3.txt")
    fen, depth = reference.read_position_file(path)
    payload = run_engine(path)
    assert payload["perft_nodes"] == reference.perft_from_fen(fen, depth, buggy=False)


def test_visible_fixtures_do_not_exercise_the_castling_divergence(run_engine):
    """Verify every visible data fixture gives the same count under the correct and naive reference."""
    for name in (
        "position.txt",
        "sanity_kr_vs_k.txt",
        "sanity_midgame_captures.txt",
        "sanity_standard_start_d3.txt",
    ):
        path = os.path.join(DATA, name)
        fen, depth = reference.read_position_file(path)
        correct = reference.perft_from_fen(fen, depth, buggy=False)
        naive = reference.perft_from_fen(fen, depth, buggy=True)
        assert correct == naive, (
            "visible fixture unexpectedly separates naive from correct: " + name
        )
