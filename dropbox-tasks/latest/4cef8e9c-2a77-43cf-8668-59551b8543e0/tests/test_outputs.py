"""Behavioral verifier for the Trickfall Matchbook Arena."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from matchbook_cases import (
    BREAKS_DURING_TABLE,
    BROKEN_TRUMP_OPTIONS,
    DEEP_GENERATED,
    DEEP_FIVE,
    DISCARD_LOSES,
    FOLLOW_REQUIRED,
    FOUR_SUIT_TIE_ORDER,
    FORCED_FOLLOW,
    GENERATED,
    ONE_TRICK,
    ONLY_TRUMP_LEAD,
    OVERTRUMP,
    OVERTRUMP_CHOICE,
    TIE_BREAK,
)
from matchbook_model import (
    Case,
    generated_case,
    initial_state,
    legal_cards,
    parse_json_lines,
    play,
    permute_suits,
    render_cases,
    rotate_seats,
    solve_case,
)

BIN = Path(os.environ.get("MATCHBOOK_BIN", "/app/matchbook/matchbook"))


def invoke(path: Path, *extra: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    """Run the submitted analyst against one verifier-owned input path."""
    return subprocess.run(
        [str(BIN), "solve", str(path), *extra],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def assert_cases(tmp_path: Path, cases: tuple[Case, ...], timeout: int = 90) -> list[dict[str, object]]:
    """Run cases and compare every output field with the independent model."""
    path = tmp_path / "arena.mbk"
    path.write_text(render_cases(cases), encoding="utf-8")
    result = invoke(path, timeout=timeout)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    observed = parse_json_lines(result.stdout)
    expected = [solve_case(case) for case in cases]
    assert observed == expected
    return observed


def assert_rejected(tmp_path: Path, text: str | bytes) -> None:
    """Assert that one malformed file is rejected atomically."""
    path = tmp_path / "invalid.mbk"
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    result = invoke(path)
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip()


def test_single_trick_has_exact_root_values_and_line(tmp_path: Path) -> None:
    """A complete one-trick analysis reports exact legal values and principal play."""
    assert_cases(tmp_path, (ONE_TRICK,))


def test_partial_follow_and_overtrump_positions(tmp_path: Path) -> None:
    """Partial tricks preserve clockwise turns, forced following, and trump winners."""
    assert_cases(tmp_path, (FORCED_FOLLOW, OVERTRUMP))


def test_void_player_can_choose_between_discarding_and_overtrumping(tmp_path: Path) -> None:
    """A void player receives both discard and higher-trump branches with exact values."""
    output = assert_cases(tmp_path, (OVERTRUMP_CHOICE,))[0]
    assert [move["card"] for move in output["moves"]] == ["C7", "DA"]
    assert output["moves"] == solve_case(OVERTRUMP_CHOICE)["moves"]


def test_follow_suit_excludes_every_off_suit_card(tmp_path: Path) -> None:
    """Holding the led suit narrows the root move list to that suit alone."""
    output = assert_cases(tmp_path, (FOLLOW_REQUIRED,))[0]
    assert output["moves"] == [{"card": "H8", "value": output["value"]}]
    assert output["best"] == "H8"


def test_high_off_suit_discard_cannot_win_the_trick(tmp_path: Path) -> None:
    """A high discard remains unable to beat a lower card of the led suit."""
    output = assert_cases(tmp_path, (DISCARD_LOSES,))[0]
    assert output["value"] == 0
    assert output["line"][0] == "CA"


def test_trump_can_break_inside_the_supplied_partial_table(tmp_path: Path) -> None:
    """A legal partial trick can change an initially unbroken trump state."""
    assert BREAKS_DURING_TABLE.broken is False
    assert any(card[0] == BREAKS_DURING_TABLE.trump for card in BREAKS_DURING_TABLE.table)
    assert_cases(tmp_path, (BREAKS_DURING_TABLE,))


def test_unbroken_trump_and_canonical_ties(tmp_path: Path) -> None:
    """Unbroken-trump leadership and equal-value canonical choices are exact."""
    outputs = assert_cases(tmp_path, (ONLY_TRUMP_LEAD, TIE_BREAK))
    assert outputs[0]["moves"] == solve_case(ONLY_TRUMP_LEAD)["moves"]
    assert outputs[1]["best"] == solve_case(TIE_BREAK)["best"]


def test_broken_state_controls_whether_trump_can_be_led(tmp_path: Path) -> None:
    """A mixed hand may lead trump only after the case marks trump as broken."""
    unbroken = replace(BROKEN_TRUMP_OPTIONS, ident="unbroken_options", broken=False)
    output = assert_cases(tmp_path, (unbroken, BROKEN_TRUMP_OPTIONS))
    unbroken_cards = [move["card"] for move in output[0]["moves"]]
    broken_cards = [move["card"] for move in output[1]["moves"]]
    assert unbroken_cards == ["H8"]
    assert broken_cards == ["C7", "H8"]


def test_equal_rank_cards_use_the_complete_suit_tie_order(tmp_path: Path) -> None:
    """Equal-ranked legal cards are listed in the documented S-H-D-C suit order."""
    output = assert_cases(tmp_path, (FOUR_SUIT_TIE_ORDER,))[0]
    assert [move["card"] for move in output["moves"]] == ["S7", "H7", "D7", "C7"]


@pytest.mark.parametrize("case", GENERATED, ids=lambda case: case.ident)
def test_generated_hidden_positions_match_independent_minimax(tmp_path: Path, case: Case) -> None:
    """Generated full and partial positions require exact optimal partnership play."""
    assert_cases(tmp_path, (case,))


def test_deep_five_trick_position_requires_complete_search(tmp_path: Path) -> None:
    """A five-trick position is solved through its final card without truncation."""
    output = assert_cases(tmp_path, (DEEP_FIVE,), timeout=180)[0]
    assert len(output["line"]) == 20
    assert len(output["moves"]) == len(solve_case(DEEP_FIVE)["moves"])


@pytest.mark.parametrize("case", DEEP_GENERATED, ids=lambda case: case.ident)
def test_generated_five_trick_games_require_deep_optimal_lines(tmp_path: Path, case: Case) -> None:
    """Hidden five-trick games require exact values and every remaining play."""
    output = assert_cases(tmp_path, (case,), timeout=180)[0]
    assert len(output["line"]) == sum(len(hand) for hand in case.hands)


def test_reported_principal_line_replays_legally_to_its_value(tmp_path: Path) -> None:
    """The reported line consumes every card legally and realizes the reported trick value."""
    case = DEEP_GENERATED[0]
    output = assert_cases(tmp_path, (case,), timeout=180)[0]
    state = initial_state(case)
    won = 0
    for card in output["line"]:
        assert card in legal_cards(state, case.trump)
        state, winner = play(state, card, case.trump)
        won += int(winner is not None and winner % 2 == case.maximize)
    assert all(not hand for hand in state.hands)
    assert state.table == ()
    assert won == output["value"]


def test_principal_line_conserves_the_remaining_card_multiset(tmp_path: Path) -> None:
    """A principal line contains every remaining held card exactly once and no table card."""
    case = DEEP_GENERATED[3]
    output = assert_cases(tmp_path, (case,), timeout=180)[0]
    held = [card for hand in case.hands for card in hand]
    assert len(output["line"]) == len(held)
    assert len(set(output["line"])) == len(output["line"])
    assert sorted(output["line"]) == sorted(held)
    assert set(output["line"]).isdisjoint(case.table)


def test_optimal_choice_is_not_a_greedy_high_card_rule(tmp_path: Path) -> None:
    """A strategic position chooses a lower card that has a strictly better value."""
    case = GENERATED[4]
    output = assert_cases(tmp_path, (case,))[0]
    values = {move["card"]: move["value"] for move in output["moves"]}
    assert output["best"] == "CT"
    assert values["CT"] > values["DQ"]


def test_opposing_seat_selects_the_minimizing_continuation(tmp_path: Path) -> None:
    """A seat outside the named team chooses the branch with the lower team value."""
    case = GENERATED[3]
    output = assert_cases(tmp_path, (case,))[0]
    values = {move["card"]: move["value"] for move in output["moves"]}
    assert output["turn"] % 2 != case.maximize
    assert output["best"] == "S8"
    assert values["S8"] < values["CT"]


def test_opposite_maximizing_teams_have_complementary_values(tmp_path: Path) -> None:
    """Solving the same zero-sum position for either team partitions all remaining tricks."""
    team_zero = generated_case(903, 4, 2, 0, ident="duality_zero")
    team_one = replace(team_zero, ident="duality_one", maximize=1)
    output = assert_cases(tmp_path, (team_zero, team_one))
    assert output[0]["value"] + output[1]["value"] == team_zero.tricks


def test_multi_case_order_and_state_isolation(tmp_path: Path) -> None:
    """A mixed batch retains input order and does not leak state between cases."""
    cases = (GENERATED[3], ONE_TRICK, GENERATED[0], FORCED_FOLLOW)
    output = assert_cases(tmp_path, cases)
    assert [record["case"] for record in output] == [case.ident for case in cases]


def test_large_mixed_batch_matches_each_independent_analysis(tmp_path: Path) -> None:
    """A larger batch spanning every depth and partial-table size remains fully isolated."""
    cases = tuple(
        generated_case(
            1500 + index,
            1 + index % 5,
            index % 4,
            index % 2,
            ident=f"batch_{index}",
        )
        for index in range(20)
    )
    output = assert_cases(tmp_path, cases, timeout=240)
    assert len(output) == len(cases)
    assert [record["case"] for record in output] == [case.ident for case in cases]


def test_every_leader_trump_and_team_combination_is_independent(tmp_path: Path) -> None:
    """All seats, trump suits, and maximizing teams receive exact independent analyses."""
    cases = tuple(
        replace(
            ONE_TRICK,
            ident=f"matrix_{leader}_{trump}_{maximize}",
            leader=leader,
            trump=trump,
            broken=True,
            maximize=maximize,
        )
        for leader in range(4)
        for trump in "SHDC"
        for maximize in range(2)
    )
    output = assert_cases(tmp_path, cases)
    assert len(output) == 32


def test_repeated_state_with_distinct_ids_is_recomputed_independently(tmp_path: Path) -> None:
    """Equivalent states with distinct identifiers produce matching analyses and distinct IDs."""
    first = generated_case(1601, 4, 3, 1, ident="repeat_alpha")
    second = replace(first, ident="repeat_beta")
    output = assert_cases(tmp_path, (first, second))
    assert output[0]["case"] == "repeat_alpha"
    assert output[1]["case"] == "repeat_beta"
    assert {**output[0], "case": None} == {**output[1], "case": None}


def test_repeated_evaluation_is_byte_deterministic(tmp_path: Path) -> None:
    """Repeated evaluation of the same batch produces byte-identical JSON Lines."""
    path = tmp_path / "repeat.mbk"
    path.write_text(render_cases((GENERATED[5], TIE_BREAK)), encoding="utf-8")
    first = invoke(path)
    second = invoke(path)
    assert first.returncode == second.returncode == 0
    assert first.stderr == second.stderr == ""
    assert first.stdout == second.stdout


def test_suit_permutation_is_solved_as_a_fresh_position(tmp_path: Path) -> None:
    """A suit-renamed position receives its independently mapped optimal response."""
    base = generated_case(701, 3, 2, 0, ident="suit_base")
    changed = permute_suits(base, "DCSH", "suit_changed")
    assert_cases(tmp_path, (base, changed))


def test_seat_rotation_preserves_partnership_game_value(tmp_path: Path) -> None:
    """Rotating seats and the maximizing partnership preserves the strategic value."""
    base = generated_case(702, 3, 1, 1, ident="rotate_base")
    changed = rotate_seats(base, 1, "rotate_changed")
    output = assert_cases(tmp_path, (base, changed))
    assert output[0]["value"] == output[1]["value"]


def test_hand_card_token_order_does_not_change_analysis(tmp_path: Path) -> None:
    """Reordering cards inside hand directives leaves the game state and result unchanged."""
    base = generated_case(904, 4, 1, 0, ident="order_forward")
    reversed_case = replace(
        base,
        ident="order_reversed",
        hands=tuple(tuple(reversed(hand)) for hand in base.hands),
    )
    output = assert_cases(tmp_path, (base, reversed_case))
    first = {**output[0], "case": "same"}
    second = {**output[1], "case": "same"}
    assert first == second


@pytest.mark.parametrize(
    "case",
    (FOLLOW_REQUIRED, BROKEN_TRUMP_OPTIONS, GENERATED[4], DEEP_GENERATED[1]),
    ids=lambda case: case.ident,
)
def test_root_moves_are_complete_legal_unique_and_canonical(tmp_path: Path, case: Case) -> None:
    """Representative root lists contain every legal card once in canonical protocol order."""
    output = assert_cases(tmp_path, (case,), timeout=180)[0]
    reported = [move["card"] for move in output["moves"]]
    expected = list(legal_cards(initial_state(case), case.trump))
    assert reported == expected
    assert len(reported) == len(set(reported))
    assert output["best"] in reported
    assert output["line"][0] == output["best"]


BASE = render_cases((ONE_TRICK,))


@pytest.mark.parametrize(
    "bad_text",
    [
        "",
        "\ufeff" + BASE,
        " \t\r\n\v\f",
        "matchbook 1\n",
        "matchbook 2\n" + "\n".join(BASE.splitlines()[1:]) + "\n",
        BASE.replace("case one_trick", "case bad.id"),
        BASE.replace("case one_trick", "case"),
        BASE.replace("case one_trick", "case naïve"),
        BASE.replace("case one_trick", "case " + "x" * 33),
        BASE.replace("trump S", "trump X"),
        BASE.replace("trump S", "Trump S"),
        BASE.replace("trump S", "trump S\x00"),
        BASE.replace("broken false", "broken False"),
        BASE.replace("leader 0", "leader 4"),
        BASE.replace("leader 0", "leader -1"),
        BASE.replace("leader 0", "leader +0"),
        BASE.replace("maximize 0", "maximize 2"),
        BASE.replace("tricks 1", "tricks 0"),
        BASE.replace("tricks 1", "tricks 6"),
        BASE.replace("hand 1 H8", "hand 1 H7"),
        BASE.replace("hand 0 H7", "hand 0 H7 H7"),
        BASE.replace("table", "table H7"),
        BASE.replace("table", "table H7 H7"),
        BASE.replace("hand 0 H7", "hand 0 H6"),
        BASE.replace("hand 0 H7", "hand 0 h7"),
        BASE.replace("hand 3 H9", "hand 3"),
        BASE.replace("hand 0 H7", "hand 1 H7"),
        BASE.replace("table", "table S7 H7 D7 C7"),
        BASE.replace("trump S", "trump S extra"),
        BASE.replace("end", "end extra"),
        BASE.replace("end\n", ""),
        BASE + "unknown\n",
        BASE + "matchbook 1\n",
        BASE + "\n" + "\n".join(BASE.splitlines()[1:]) + "\n",
        BASE.replace("matchbook 1", "matchbook 1\n# comment"),
        BASE.replace("trump S", "trump\u00a0S"),
        BASE.replace("trump S", "\u00a0trump S"),
        BASE.replace("trump S", "trump S\u00a0"),
    ],
    ids=[
        "empty",
        "utf8-bom",
        "whitespace-only",
        "header-only",
        "version",
        "identifier",
        "missing-identifier",
        "non-ascii-identifier",
        "long-identifier",
        "trump",
        "directive-case",
        "nul-token",
        "boolean",
        "leader",
        "negative-leader",
        "signed-leader",
        "team",
        "zero-depth",
        "excess-depth",
        "duplicate-card",
        "same-hand-duplicate",
        "table-hand-duplicate",
        "same-table-duplicate",
        "card-code",
        "lowercase-card",
        "hand-size",
        "hand-order",
        "table-length",
        "trailing-token",
        "end-trailing-token",
        "missing-end",
        "trailing-data",
        "duplicate-header",
        "duplicate-id",
        "comment",
        "non-ascii-separator",
        "non-ascii-leading-space",
        "non-ascii-trailing-space",
    ],
)
def test_malformed_grammar_and_state_are_atomic(tmp_path: Path, bad_text: str) -> None:
    """Malformed grammar, ranges, duplication, and state reject the entire file."""
    assert_rejected(tmp_path, bad_text)


def test_illegal_partial_follow_is_rejected(tmp_path: Path) -> None:
    """A partial table that violates follow-suit is an impossible input state."""
    text = """matchbook 1
case illegal_follow
trump S
broken true
leader 0
maximize 0
tricks 2
table H7 C7
hand 0 S7
hand 1 H8
hand 2 D7 D8
hand 3 C8 C9
end
"""
    assert_rejected(tmp_path, text)


def test_illegal_unbroken_trump_lead_is_rejected(tmp_path: Path) -> None:
    """A trump lead is impossible when trump was unbroken and plain cards were held."""
    text = """matchbook 1
case illegal_lead
trump S
broken false
leader 0
maximize 1
tricks 2
table S7
hand 0 H7
hand 1 H8 S8
hand 2 H9 S9
hand 3 HT ST
end
"""
    assert_rejected(tmp_path, text)


def test_late_invalid_case_rejects_all_prior_valid_results(tmp_path: Path) -> None:
    """An invalid final case prevents output for valid cases parsed earlier in the file."""
    valid_prefix = render_cases((GENERATED[0], GENERATED[1])).rstrip("\n")
    invalid_tail = render_cases((ONE_TRICK,)).splitlines()[1:]
    invalid_tail[1] = "trump X"
    assert_rejected(tmp_path, valid_prefix + "\n" + "\n".join(invalid_tail) + "\n")


def test_non_utf8_and_unreadable_files_are_rejected(tmp_path: Path) -> None:
    """Invalid UTF-8 and unreadable paths fail with no partial standard output."""
    assert_rejected(tmp_path, b"matchbook 1\n\xff\n")
    missing = invoke(tmp_path / "missing.mbk")
    assert missing.returncode != 0
    assert missing.stdout == ""
    assert missing.stderr.strip()


def test_invalid_invocations_are_rejected(tmp_path: Path) -> None:
    """Missing, unknown, or surplus command arguments are rejected consistently."""
    path = tmp_path / "valid.mbk"
    path.write_text(BASE, encoding="utf-8")
    commands = ([str(BIN)], [str(BIN), "other", str(path)], [str(BIN), "solve", str(path), "extra"])
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        assert result.returncode != 0
        assert result.stdout == ""
        assert result.stderr.strip()


def test_blank_lines_and_ascii_whitespace_are_accepted(tmp_path: Path) -> None:
    """Blank lines and varied ASCII token spacing retain the same case semantics."""
    text = BASE.replace("matchbook 1\n", "\nmatchbook 1\n\n").replace("trump S", "trump\tS")
    path = tmp_path / "spacing.mbk"
    path.write_text(text, encoding="utf-8")
    result = invoke(path)
    assert result.returncode == 0, result.stderr
    assert parse_json_lines(result.stdout) == [solve_case(ONE_TRICK)]


def test_boundary_identifier_crlf_and_missing_final_newline_are_accepted(tmp_path: Path) -> None:
    """A maximum-length identifier and ordinary UTF-8 text boundaries remain valid input."""
    case = replace(ONE_TRICK, ident="A_b-" * 8)
    text = render_cases((case,)).rstrip("\n").replace("\n", "\r\n")
    path = tmp_path / "boundaries.mbk"
    path.write_bytes(text.encode("utf-8"))
    result = invoke(path)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert parse_json_lines(result.stdout) == [solve_case(case)]


def test_json_schema_has_no_missing_or_extra_fields(tmp_path: Path) -> None:
    """Every success record has exactly the documented nested JSON schema."""
    record = assert_cases(tmp_path, (GENERATED[1],))[0]
    assert set(record) == {"case", "turn", "moves", "best", "value", "line"}
    assert all(set(move) == {"card", "value"} for move in record["moves"])
    assert type(record["turn"]) is int
    assert type(record["value"]) is int
    assert isinstance(record["case"], str)
    assert isinstance(record["best"], str)
    assert isinstance(record["line"], list)
    assert all(isinstance(card, str) for card in record["line"])
    assert isinstance(record["moves"], list) and record["moves"]
    assert all(isinstance(move["card"], str) for move in record["moves"])
    assert all(type(move["value"]) is int for move in record["moves"])
    json.dumps(record, allow_nan=False)
