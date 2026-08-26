import pytest

import reference


def test_hidden_manifest_lists_at_least_five_cases():
    """Verify the hidden fixture manifest lists at least five distinct held-back cases."""
    assert len(reference.hidden_case_names()) >= 5


@pytest.mark.parametrize("case_name", reference.hidden_case_names())
def test_held_back_position_matches_independent_reference(run_engine, case_name):
    """Verify the engine's output on each held-back position matches the independent reference."""
    path = reference.hidden_case_path(case_name)
    fen, depth = reference.read_position_file(path)
    payload = run_engine(path)
    assert payload["perft_nodes"] == reference.perft_from_fen(fen, depth, buggy=False)
