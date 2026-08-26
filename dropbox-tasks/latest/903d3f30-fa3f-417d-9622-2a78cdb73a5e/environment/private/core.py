"""Canonical Tidevault v1 rules and deterministic state serialization."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Iterable, Optional


PROTOCOL = "arena-tidevault-v1"
RULESET = "tidevault-v1"
COLORS = ("gold", "violet")
RINGS = ("I", "M", "O")
SECTORS = ("A", "B", "C", "D", "E", "F")
DIRECTIONS = ("CW", "CCW")
POWERS = (1, 2, 3)
PLY_LIMIT = 18
TIDE_PLIES = (9, 18)
INITIAL_INVENTORY = (3, 3, 3)
SLOTS = tuple(f"{ring}{sector}" for ring in RINGS for sector in SECTORS)

_ACTION_RE = re.compile(r"^P([123]) ([IMO])([A-F]) ([IMO]) (CW|CCW)$")
_STONE_ID_RE = re.compile(r"^S(0[1-9]|1[0-8])$")


def other(color: str) -> str:
    """Return the opposing color."""

    if color == "gold":
        return "violet"
    if color == "violet":
        return "gold"
    raise ValueError(f"unknown color: {color!r}")


def slot_index(ring: str, sector: str) -> int:
    """Return the ring-major board index for one canonical slot."""

    try:
        return RINGS.index(ring) * len(SECTORS) + SECTORS.index(sector)
    except ValueError as error:
        raise ValueError("slot must use ring I/M/O and sector A-F") from error


def slot_name(ring: str, sector: str) -> str:
    """Return one canonical two-character slot name."""

    slot_index(ring, sector)
    return f"{ring}{sector}"


def parse_slot(slot: str) -> tuple[str, str]:
    """Parse an exact canonical slot name."""

    if not isinstance(slot, str) or len(slot) != 2:
        raise ValueError("slot must be one of IA through OF")
    ring, sector = slot
    if slot_name(ring, sector) != slot:
        raise ValueError("slot is not canonical")
    return ring, sector


@dataclass(frozen=True, order=True)
class Action:
    """One atomic placement followed by one ring rotation."""

    power: int
    placement_ring: str
    placement_sector: str
    rotation_ring: str
    direction: str

    def __post_init__(self) -> None:
        if self.power not in POWERS:
            raise ValueError("power must be 1, 2, or 3")
        slot_index(self.placement_ring, self.placement_sector)
        if self.rotation_ring not in RINGS:
            raise ValueError("rotation ring must be I, M, or O")
        if self.direction not in DIRECTIONS:
            raise ValueError("direction must be CW or CCW")

    @property
    def placement_slot(self) -> str:
        """Return the pre-rotation placement slot."""

        return slot_name(self.placement_ring, self.placement_sector)

    @property
    def token(self) -> str:
        """Return the public canonical action token."""

        return (
            f"P{self.power} {self.placement_slot} "
            f"{self.rotation_ring} {self.direction}"
        )


def settled_slot_for_action(action: Action) -> str:
    """Return the new stone's slot immediately after its action's rotation."""

    if action.placement_ring != action.rotation_ring:
        return action.placement_slot
    sector = SECTORS.index(action.placement_sector)
    delta = 1 if action.direction == "CW" else -1
    return slot_name(action.placement_ring, SECTORS[(sector + delta) % len(SECTORS)])


@dataclass(frozen=True)
class Stone:
    """One immutable owned, weighted stone on the board."""

    stone_id: str
    owner: str
    power: int

    def __post_init__(self) -> None:
        if not isinstance(self.stone_id, str) or _STONE_ID_RE.fullmatch(self.stone_id) is None:
            raise ValueError("stone ID must be S01 through S18")
        if self.owner not in COLORS:
            raise ValueError("stone owner must be gold or violet")
        if self.power not in POWERS:
            raise ValueError("stone power must be 1, 2, or 3")


@dataclass(frozen=True)
class Move:
    """Immutable evidence for one accepted action."""

    stone_id: str
    owner: str
    action: Action
    placed_slot: str
    settled_slot: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, Action):
            raise ValueError("move action is malformed")
        Stone(self.stone_id, self.owner, self.action.power)
        if self.placed_slot != self.action.placement_slot:
            raise ValueError("move placed slot differs from its action")
        if self.settled_slot != settled_slot_for_action(self.action):
            raise ValueError("move settled slot differs from its rotation")


@dataclass(frozen=True)
class SpokeScore:
    """Post-rotation scoring evidence for one radial spoke."""

    sector: str
    gold_weight: int
    violet_weight: int
    point_owner: Optional[str]

    def __post_init__(self) -> None:
        if self.sector not in SECTORS:
            raise ValueError("spoke sector must be A through F")
        if (
            type(self.gold_weight) is not int
            or type(self.violet_weight) is not int
            or self.gold_weight < 0
            or self.violet_weight < 0
        ):
            raise ValueError("spoke weights must be nonnegative integers")
        expected: Optional[str]
        if self.gold_weight > self.violet_weight:
            expected = "gold"
        elif self.violet_weight > self.gold_weight:
            expected = "violet"
        else:
            expected = None
        if self.point_owner != expected:
            raise ValueError("spoke point owner differs from its weights")


@dataclass(frozen=True)
class Tide:
    """Immutable evidence for one six-spoke scoring tide."""

    tide: int
    ply: int
    gold_points: int
    violet_points: int
    spokes: tuple[SpokeScore, ...]

    def __post_init__(self) -> None:
        if type(self.tide) is not int or not 1 <= self.tide <= len(TIDE_PLIES):
            raise ValueError("tide number must be 1 or 2")
        if self.ply != TIDE_PLIES[self.tide - 1]:
            raise ValueError("tide ply does not match its number")
        if len(self.spokes) != len(SECTORS) or tuple(
            spoke.sector for spoke in self.spokes
        ) != SECTORS:
            raise ValueError("tide spokes must be in canonical sector order")
        if self.gold_points != sum(
            spoke.point_owner == "gold" for spoke in self.spokes
        ) or self.violet_points != sum(
            spoke.point_owner == "violet" for spoke in self.spokes
        ):
            raise ValueError("tide point totals differ from its spokes")


@dataclass(frozen=True)
class State:
    """Complete immutable native Tidevault state."""

    turn: str = "gold"
    ply: int = 0
    gold_score: int = 0
    violet_score: int = 0
    gold_inventory: tuple[int, int, int] = INITIAL_INVENTORY
    violet_inventory: tuple[int, int, int] = INITIAL_INVENTORY
    board: tuple[Optional[Stone], ...] = (None,) * len(SLOTS)
    moves: tuple[Move, ...] = ()
    tides: tuple[Tide, ...] = ()
    result: str = "ongoing"
    winner: Optional[str] = None
    termination: Optional[str] = None

    @property
    def terminal(self) -> bool:
        """Return whether native play has ended."""

        return self.result != "ongoing"

    def score(self, color: str) -> int:
        """Return one color's cumulative tide score."""

        if color == "gold":
            return self.gold_score
        if color == "violet":
            return self.violet_score
        raise ValueError(f"unknown color: {color!r}")

    def inventory(self, color: str) -> tuple[int, int, int]:
        """Return one color's P1/P2/P3 inventory."""

        if color == "gold":
            return self.gold_inventory
        if color == "violet":
            return self.violet_inventory
        raise ValueError(f"unknown color: {color!r}")


def initial_state() -> State:
    """Construct the unique Tidevault opening."""

    return State()


def format_action(action: Action) -> str:
    """Format an action in canonical public form."""

    return action.token


def parse_action(token: str) -> Action:
    """Parse one exact canonical action token."""

    if not isinstance(token, str):
        raise ValueError("action must be a string")
    match = _ACTION_RE.fullmatch(token)
    if match is None:
        raise ValueError("action must look like `P2 IA M CW`")
    action = Action(
        int(match.group(1)),
        match.group(2),
        match.group(3),
        match.group(4),
        match.group(5),
    )
    if action.token != token:
        raise ValueError("action is not canonical")
    return action


def action_from_parts(
    power: str,
    placement_slot: str,
    rotation_ring: str,
    direction: str,
) -> Action:
    """Parse the four public move arguments as one canonical action."""

    return parse_action(f"{power} {placement_slot} {rotation_ring} {direction}")


def stone_at(state: State, ring: str, sector: str) -> Optional[Stone]:
    """Return the stone occupying one slot, if any."""

    return state.board[slot_index(ring, sector)]


def current_slot(state: State, stone_id: str) -> Optional[str]:
    """Return a stone's current slot, or None when it is absent."""

    for index, stone in enumerate(state.board):
        if stone is not None and stone.stone_id == stone_id:
            return SLOTS[index]
    return None


def is_legal(state: State, action: Action, actor: Optional[str] = None) -> bool:
    """Return whether actor may take action in state."""

    color = state.turn if actor is None else actor
    if color not in COLORS or state.terminal or not isinstance(action, Action):
        return False
    return (
        state.inventory(color)[action.power - 1] > 0
        and stone_at(state, action.placement_ring, action.placement_sector) is None
    )


def legal_actions(state: State, actor: Optional[str] = None) -> tuple[Action, ...]:
    """Enumerate legal actions in the frozen canonical order."""

    color = state.turn if actor is None else actor
    if color not in COLORS or state.terminal:
        return ()
    inventory = state.inventory(color)
    actions: list[Action] = []
    for power in POWERS:
        if inventory[power - 1] <= 0:
            continue
        for placement_ring in RINGS:
            for placement_sector in SECTORS:
                if stone_at(state, placement_ring, placement_sector) is not None:
                    continue
                for rotation_ring in RINGS:
                    for direction in DIRECTIONS:
                        actions.append(
                            Action(
                                power,
                                placement_ring,
                                placement_sector,
                                rotation_ring,
                                direction,
                            )
                        )
    return tuple(actions)


def _rotate(board: list[Optional[Stone]], ring: str, direction: str) -> None:
    base = slot_index(ring, "A")
    old = board[base : base + len(SECTORS)]
    delta = 1 if direction == "CW" else -1
    for old_sector, stone in enumerate(old):
        board[base + (old_sector + delta) % len(SECTORS)] = stone


def score_spokes(board: tuple[Optional[Stone], ...]) -> tuple[SpokeScore, ...]:
    """Score all six spokes from one post-rotation board."""

    if len(board) != len(SLOTS):
        raise ValueError("board must contain exactly 18 cells")
    spokes: list[SpokeScore] = []
    for sector in SECTORS:
        gold_weight = 0
        violet_weight = 0
        for ring in RINGS:
            stone = board[slot_index(ring, sector)]
            if stone is None:
                continue
            if stone.owner == "gold":
                gold_weight += stone.power
            else:
                violet_weight += stone.power
        point_owner: Optional[str]
        if gold_weight > violet_weight:
            point_owner = "gold"
        elif violet_weight > gold_weight:
            point_owner = "violet"
        else:
            point_owner = None
        spokes.append(SpokeScore(sector, gold_weight, violet_weight, point_owner))
    return tuple(spokes)


def _finish(state: State) -> State:
    if state.gold_score > state.violet_score:
        return replace(state, result="gold_win", winner="gold", termination="complete")
    if state.violet_score > state.gold_score:
        return replace(
            state,
            result="violet_win",
            winner="violet",
            termination="complete",
        )
    return replace(state, result="draw", winner=None, termination="complete")


def apply_action(state: State, action: Action) -> State:
    """Apply one legal placement and rotation atomically."""

    actor = state.turn
    if not is_legal(state, action, actor):
        raise ValueError("illegal action")
    stone_id = f"S{state.ply + 1:02d}"
    stone = Stone(stone_id, actor, action.power)
    board = list(state.board)
    board[slot_index(action.placement_ring, action.placement_sector)] = stone
    _rotate(board, action.rotation_ring, action.direction)
    settled_slot = settled_slot_for_action(action)
    if current_slot(replace(state, board=tuple(board)), stone_id) != settled_slot:
        raise RuntimeError("placed stone did not settle in its recorded slot")

    inventory = list(state.inventory(actor))
    inventory[action.power - 1] -= 1
    move = Move(stone_id, actor, action, action.placement_slot, settled_slot)
    ply = state.ply + 1
    gold_score = state.gold_score
    violet_score = state.violet_score
    tides = state.tides
    if ply in TIDE_PLIES:
        spokes = score_spokes(tuple(board))
        gold_points = sum(spoke.point_owner == "gold" for spoke in spokes)
        violet_points = sum(spoke.point_owner == "violet" for spoke in spokes)
        tides += (
            Tide(
                tide=TIDE_PLIES.index(ply) + 1,
                ply=ply,
                gold_points=gold_points,
                violet_points=violet_points,
                spokes=spokes,
            ),
        )
        gold_score += gold_points
        violet_score += violet_points

    next_state = replace(
        state,
        ply=ply,
        gold_score=gold_score,
        violet_score=violet_score,
        gold_inventory=tuple(inventory) if actor == "gold" else state.gold_inventory,
        violet_inventory=(
            tuple(inventory) if actor == "violet" else state.violet_inventory
        ),
        board=tuple(board),
        moves=state.moves + (move,),
        tides=tides,
    )
    if ply == PLY_LIMIT:
        return _finish(next_state)
    return replace(next_state, turn=other(actor))


def _stone_object(stone: Optional[Stone]) -> Optional[dict[str, object]]:
    if stone is None:
        return None
    return {"owner": stone.owner, "power": stone.power, "stone_id": stone.stone_id}


def _move_object(move: Move) -> dict[str, object]:
    return {
        "action": move.action.token,
        "owner": move.owner,
        "placed_slot": move.placed_slot,
        "settled_slot": move.settled_slot,
        "stone_id": move.stone_id,
    }


def _spoke_object(spoke: SpokeScore) -> dict[str, object]:
    return {
        "gold_weight": spoke.gold_weight,
        "point_owner": spoke.point_owner,
        "sector": spoke.sector,
        "violet_weight": spoke.violet_weight,
    }


def _tide_object(tide: Tide) -> dict[str, object]:
    return {
        "gold_points": tide.gold_points,
        "ply": tide.ply,
        "spokes": [_spoke_object(spoke) for spoke in tide.spokes],
        "tide": tide.tide,
        "violet_points": tide.violet_points,
    }


def canonical_state_object(state: State) -> dict[str, object]:
    """Return the exact native-hash object, excluding outcome overlays."""

    return {
        "board": [_stone_object(stone) for stone in state.board],
        "inventories": [list(state.gold_inventory), list(state.violet_inventory)],
        "moves": [_move_object(move) for move in state.moves],
        "ply": state.ply,
        "ruleset": RULESET,
        "scores": [state.gold_score, state.violet_score],
        "tides": [_tide_object(tide) for tide in state.tides],
        "turn": state.turn,
    }


def canonical_serialize(state: State) -> str:
    """Serialize native state for hashing and protected-engine transport."""

    return json.dumps(
        canonical_state_object(state),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def state_hash(state: State) -> str:
    """Return the lowercase SHA-256 native state digest."""

    return hashlib.sha256(canonical_serialize(state).encode("ascii")).hexdigest()


def state_from_object(value: object) -> State:
    """Parse and validate one canonical native-hash object."""

    if not isinstance(value, dict) or set(value) != {
        "board",
        "inventories",
        "moves",
        "ply",
        "ruleset",
        "scores",
        "tides",
        "turn",
    }:
        raise ValueError("state object has the wrong keys")
    if value.get("ruleset") != RULESET:
        raise ValueError("state object has the wrong ruleset")
    raw_moves = value.get("moves")
    if not isinstance(raw_moves, list):
        raise ValueError("state moves must be a list")
    replayed = initial_state()
    for raw_move in raw_moves:
        if not isinstance(raw_move, dict) or set(raw_move) != {
            "action",
            "owner",
            "placed_slot",
            "settled_slot",
            "stone_id",
        }:
            raise ValueError("state object has a malformed move")
        if raw_move["owner"] != replayed.turn:
            raise ValueError("recorded move owner is out of turn")
        replayed = apply_action(replayed, parse_action(raw_move["action"]))
    serialized = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if canonical_serialize(replayed) != serialized:
        raise ValueError("state object differs from canonical replay")
    return replayed


def state_from_serialized(serialized: str) -> State:
    """Parse exact canonical serialization used by the protected engine."""

    try:
        value = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise ValueError("state serialization is not JSON") from error
    state = state_from_object(value)
    if canonical_serialize(state) != serialized:
        raise ValueError("state serialization is not canonical")
    return state


def validate_state(state: State) -> None:
    """Raise ValueError unless state is a self-consistent reachable prefix."""

    if not isinstance(state, State):
        raise ValueError("state has the wrong type")
    if state.turn not in COLORS or type(state.ply) is not int:
        raise ValueError("invalid turn or ply")
    if not 0 <= state.ply <= PLY_LIMIT or len(state.board) != len(SLOTS):
        raise ValueError("invalid ply or board size")
    if len(state.moves) != state.ply:
        raise ValueError("move count differs from ply")
    expected = initial_state()
    for move in state.moves:
        if move.owner != expected.turn:
            raise ValueError("recorded move owner is out of turn")
        expected = apply_action(expected, move.action)
        if expected.moves[-1] != move:
            raise ValueError("recorded move evidence differs from replay")
    fields = (
        "turn",
        "ply",
        "gold_score",
        "violet_score",
        "gold_inventory",
        "violet_inventory",
        "board",
        "moves",
        "tides",
        "result",
        "winner",
        "termination",
    )
    if any(getattr(state, field) != getattr(expected, field) for field in fields):
        raise ValueError("state differs from canonical replay")


def play(actions: Iterable[Action]) -> State:
    """Replay an action iterable from the unique opening."""

    state = initial_state()
    for action in actions:
        state = apply_action(state, action)
    return state


def _selftest() -> None:
    state = initial_state()
    assert len(legal_actions(state)) == 324
    action = parse_action("P2 IA I CW")
    assert action == Action(2, "I", "A", "I", "CW")
    state = apply_action(state, action)
    assert current_slot(state, "S01") == "IB"
    assert state.moves[-1].placed_slot == "IA"
    assert state.moves[-1].settled_slot == "IB"
    for _ in range(8):
        state = apply_action(state, legal_actions(state)[0])
    assert state.ply == 9 and len(state.tides) == 1
    assert state.gold_score + state.violet_score <= 6
    serialized = canonical_serialize(state)
    assert state_from_serialized(serialized) == state
    validate_state(state)
    assert len(state_hash(state)) == 64


if __name__ == "__main__":
    _selftest()
