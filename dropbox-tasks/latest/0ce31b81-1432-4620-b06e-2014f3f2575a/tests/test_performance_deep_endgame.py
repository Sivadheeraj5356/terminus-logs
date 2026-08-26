import os

import reference

PERFORMANCE_TIMEOUT_SEC = 30
PERFORMANCE_CASE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "hidden",
    "hidden_performance_deep_rook_king_endgame.txt",
)


def test_deep_endgame_completes_in_time_and_matches_reference(run_engine):
    """A held-back long-sliding king/rook endgame at a much greater depth than any visible sample finishes within the efficiency budget and matches the independent reference."""
    fen, depth = reference.read_position_file(PERFORMANCE_CASE_PATH)
    correct = reference.perft_from_fen(fen, depth, buggy=False)
    payload = run_engine(PERFORMANCE_CASE_PATH, timeout=PERFORMANCE_TIMEOUT_SEC)
    assert payload["perft_nodes"] == correct
