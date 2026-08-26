import pytest

import reference

TRAP_CASES = [
    "hidden_combined_seed",
    "hidden_bug1_only_queenside",
    "hidden_bug2_only_kingside_capture",
    "hidden_black_side_castles",
    "hidden_different_files_bug1",
]


@pytest.mark.parametrize("case_name", TRAP_CASES)
def test_agent_avoids_the_naive_castling_rule_on_trap_case(run_engine, case_name):
    """Verify the engine matches the correct perft count, not the naive castling count, on each trap case."""
    path = reference.hidden_case_path(case_name)
    fen, depth = reference.read_position_file(path)
    correct = reference.perft_from_fen(fen, depth, buggy=False)
    naive = reference.perft_from_fen(fen, depth, buggy=True)
    assert correct != naive, (
        "fixture does not separate naive from correct: " + case_name
    )
    payload = run_engine(path)
    assert payload["perft_nodes"] == correct


def test_naive_rule_agrees_with_correct_on_the_control_case(run_engine):
    """Verify the naive castling rule and the correct rule agree on a position with no overlap or capture trap."""
    path = reference.hidden_case_path("hidden_control_no_trap")
    fen, depth = reference.read_position_file(path)
    correct = reference.perft_from_fen(fen, depth, buggy=False)
    naive = reference.perft_from_fen(fen, depth, buggy=True)
    assert correct == naive
    payload = run_engine(path)
    assert payload["perft_nodes"] == correct


def test_trap_case_divergence_margins_are_not_uniform():
    """Verify the naive-versus-correct divergence differs in size across the trap cases."""
    margins = set()
    for case_name in TRAP_CASES:
        path = reference.hidden_case_path(case_name)
        fen, depth = reference.read_position_file(path)
        correct = reference.perft_from_fen(fen, depth, buggy=False)
        naive = reference.perft_from_fen(fen, depth, buggy=True)
        margins.add(naive - correct)
    assert len(margins) > 1


SHALLOW_DEPTHS_BY_CASE = {
    "hidden_combined_seed": (1, 2),
    "hidden_bug1_only_queenside": (1, 2),
    "hidden_bug2_only_kingside_capture": (1, 2),
    "hidden_black_side_castles": (1,),
    "hidden_different_files_bug1": (1, 2),
}


def test_trap_cases_match_at_shallow_depth_before_the_castling_divergence():
    """Verify each trap position's naive and correct counts agree at its validated shallow depths, before diverging deeper."""
    for case_name in TRAP_CASES:
        path = reference.hidden_case_path(case_name)
        fen, _ = reference.read_position_file(path)
        for shallow_depth in SHALLOW_DEPTHS_BY_CASE[case_name]:
            correct = reference.perft_from_fen(fen, shallow_depth, buggy=False)
            naive = reference.perft_from_fen(fen, shallow_depth, buggy=True)
            assert correct == naive, "trap case diverges too early at depth %d: %s" % (
                shallow_depth,
                case_name,
            )
