"""Independent Trickfall endgame model used by the pytest verifier."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable

SUITS = "SHDC"
RANKS = "789TJQKA"
ALL_CARDS = tuple(f"{suit}{rank}" for suit in SUITS for rank in RANKS)


def suit(card: str) -> int:
    """Return the protocol suit index for a card."""
    return SUITS.index(card[0])


def rank(card: str) -> int:
    """Return the protocol rank index for a card."""
    return RANKS.index(card[1])


def pkey(card: str) -> tuple[int, int]:
    """Return the canonical weak-to-strong comparison key."""
    return rank(card), suit(card)


@dataclass(frozen=True)
class Case:
    """Represent one complete Matchbook input case."""

    ident: str
    trump: str
    broken: bool
    leader: int
    maximize: int
    tricks: int
    table: tuple[str, ...]
    hands: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class State:
    """Represent a game-tree state after the supplied partial table."""

    hands: tuple[frozenset[str], ...]
    leader: int
    table: tuple[str, ...]
    broken: bool


def legal_cards(state: State, trump: str) -> tuple[str, ...]:
    """Return every legal card for the current seat in canonical order."""
    turn = (state.leader + len(state.table)) % 4
    hand = state.hands[turn]
    if not state.table:
        allowed = hand
        if not state.broken:
            plain = frozenset(card for card in hand if card[0] != trump)
            if plain:
                allowed = plain
    else:
        led = state.table[0][0]
        following = frozenset(card for card in hand if card[0] == led)
        allowed = following or hand
    return tuple(sorted(allowed, key=pkey))


def trick_winner(table: tuple[str, ...], leader: int, trump: str) -> int:
    """Return the winning seat for a complete trick."""
    winning_suit = trump if any(card[0] == trump for card in table) else table[0][0]
    candidates = [
        (rank(card), index)
        for index, card in enumerate(table)
        if card[0] == winning_suit
    ]
    offset = max(candidates)[1]
    return (leader + offset) % 4


def play(state: State, card: str, trump: str) -> tuple[State, int | None]:
    """Apply one legal card and return the successor and optional winner."""
    turn = (state.leader + len(state.table)) % 4
    hands = list(state.hands)
    hands[turn] = hands[turn] - {card}
    table = state.table + (card,)
    broken = state.broken or card[0] == trump
    if len(table) == 4:
        winner = trick_winner(table, state.leader, trump)
        return State(tuple(hands), winner, (), broken), winner
    return State(tuple(hands), state.leader, table, broken), None


def initial_state(case: Case) -> State:
    """Reconstruct and validate the current state from a case."""
    hands = [frozenset(hand) for hand in case.hands]
    before = list(hands)
    for index, card in enumerate(case.table):
        seat = (case.leader + index) % 4
        before[seat] = before[seat] | {card}
    state = State(tuple(before), case.leader, (), case.broken)
    for card in case.table:
        if card not in legal_cards(state, case.trump):
            raise ValueError("illegal supplied table")
        state, winner = play(state, card, case.trump)
        if winner is not None:
            raise ValueError("supplied table completed a trick")
    if state.hands != tuple(hands):
        raise ValueError("reconstruction mismatch")
    return state


def solve_case(case: Case) -> dict[str, object]:
    """Compute the exact canonical response for one case."""
    start = initial_state(case)

    @lru_cache(maxsize=None)
    def evaluate(state: State) -> tuple[int, tuple[str, ...]]:
        """Evaluate one immutable state by optimal partnership play."""
        if all(not hand for hand in state.hands):
            return 0, ()
        turn = (state.leader + len(state.table)) % 4
        options: list[tuple[str, int, tuple[str, ...]]] = []
        for card in legal_cards(state, case.trump):
            successor, winner = play(state, card, case.trump)
            child_value, child_line = evaluate(successor)
            gain = int(winner is not None and winner % 2 == case.maximize)
            options.append((card, gain + child_value, (card,) + child_line))
        target = max if turn % 2 == case.maximize else min
        optimum = target(value for _, value, _ in options)
        return next((value, line) for _, value, line in options if value == optimum)

    moves = []
    for card in legal_cards(start, case.trump):
        successor, winner = play(start, card, case.trump)
        child_value, _ = evaluate(successor)
        gain = int(winner is not None and winner % 2 == case.maximize)
        moves.append({"card": card, "value": gain + child_value})
    value, line = evaluate(start)
    return {
        "case": case.ident,
        "turn": (case.leader + len(case.table)) % 4,
        "moves": moves,
        "best": line[0],
        "value": value,
        "line": list(line),
    }


def render_cases(cases: Iterable[Case]) -> str:
    """Serialize cases using the public Matchbook grammar."""
    lines = ["matchbook 1"]
    for case in cases:
        lines.extend(
            [
                f"case {case.ident}",
                f"trump {case.trump}",
                f"broken {str(case.broken).lower()}",
                f"leader {case.leader}",
                f"maximize {case.maximize}",
                f"tricks {case.tricks}",
                "table" + (" " + " ".join(case.table) if case.table else ""),
            ]
        )
        for seat, hand in enumerate(case.hands):
            cards_text = " ".join(hand)
            lines.append(f"hand {seat}" + (f" {cards_text}" if cards_text else ""))
        lines.append("end")
    return "\n".join(lines) + "\n"


def generated_case(
    seed: int,
    tricks: int,
    partial: int,
    maximize: int,
    *,
    broken: bool | None = None,
    ident: str | None = None,
) -> Case:
    """Generate a deterministic valid position without embedding an answer."""
    rng = random.Random(seed)
    selected = rng.sample(ALL_CARDS, 4 * tricks)
    hands = [set(selected[seat * tricks : (seat + 1) * tricks]) for seat in range(4)]
    trump = rng.choice(SUITS)
    leader = rng.randrange(4)
    start_broken = rng.choice([False, True]) if broken is None else broken
    state = State(tuple(frozenset(hand) for hand in hands), leader, (), start_broken)
    table: list[str] = []
    for _ in range(partial):
        choices = legal_cards(state, trump)
        card = choices[rng.randrange(len(choices))]
        table.append(card)
        state, winner = play(state, card, trump)
        if winner is not None:
            raise AssertionError("partial generation completed a trick")
    ordered_hands = tuple(tuple(sorted(hand, key=pkey)) for hand in state.hands)
    return Case(
        ident or f"g{seed}_{tricks}_{partial}_{maximize}",
        trump,
        start_broken,
        leader,
        maximize,
        tricks,
        tuple(table),
        ordered_hands,
    )


def permute_suits(case: Case, permutation: str, ident: str) -> Case:
    """Return a position with suits renamed by a supplied permutation."""
    mapping = dict(zip(SUITS, permutation, strict=True))

    def mapped(card: str) -> str:
        """Rename one card while retaining its rank."""
        return mapping[card[0]] + card[1]

    return replace(
        case,
        ident=ident,
        trump=mapping[case.trump],
        table=tuple(mapped(card) for card in case.table),
        hands=tuple(tuple(mapped(card) for card in hand) for hand in case.hands),
    )


def rotate_seats(case: Case, amount: int, ident: str) -> Case:
    """Return an equivalent position with all seats rotated clockwise."""
    hands: list[tuple[str, ...]] = [(), (), (), ()]
    for old_seat, hand in enumerate(case.hands):
        hands[(old_seat + amount) % 4] = hand
    return replace(
        case,
        ident=ident,
        leader=(case.leader + amount) % 4,
        maximize=(case.maximize + amount) % 2,
        hands=tuple(hands),
    )


def parse_json_lines(stdout: str) -> list[dict[str, object]]:
    """Parse nonempty JSON Lines output for exact semantic comparison."""
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        """Reject duplicate JSON member names instead of silently overwriting them."""
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AssertionError(f"duplicate JSON member {key!r}")
            result[key] = value
        return result

    def invalid_constant(token: str) -> object:
        """Reject non-standard non-finite JSON constants."""
        raise AssertionError(f"invalid JSON constant {token}")

    lines = stdout.splitlines()
    if not lines:
        raise AssertionError("successful output must not be empty")
    records = [
        json.loads(line, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        for line in lines
    ]
    if not all(isinstance(record, dict) for record in records):
        raise AssertionError("each output line must be a JSON object")
    return records


def write_case_file(path: Path, cases: Iterable[Case]) -> None:
    """Write cases to a temporary verifier input file."""
    path.write_text(render_cases(cases), encoding="utf-8")
