#!/usr/bin/env python3
"""Independently replay and attest the live Tidevault referee with named tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import shlex
import socket
import stat
import subprocess
from typing import Any, Mapping, Sequence

import pytest


PROTOCOL = "arena-tidevault-v1"
RULESET = "tidevault-v1"
RINGS = ("I", "M", "O")
SECTORS = ("A", "B", "C", "D", "E", "F")
SLOTS = tuple(f"{ring}{sector}" for ring in RINGS for sector in SECTORS)
COLORS = ("gold", "violet")
POWERS = (1, 2, 3)
DIRECTIONS = ("CW", "CCW")
PLY_LIMIT = 18
TIDE_PLIES = (9, 18)
ACTION_RE = re.compile(r"P([123]) ([IMO])([A-F]) ([IMO]) (CW|CCW)\Z")
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
MODEL_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}\Z")
MAX_PUBLIC_BYTES = 1_048_576

VALUE_FEATURE_NAMES = (
    "bias", "score_diff", "ply", "tides_completed", "plies_to_tide",
    "own_p1_left", "own_p2_left", "own_p3_left", "opp_p1_left",
    "opp_p2_left", "opp_p3_left", "empty_slots", "own_board_weight",
    "opp_board_weight", "own_spoke_leads", "opp_spoke_leads",
    "tied_spokes", "own_spoke_margin", "own_max_spoke", "opp_max_spoke",
    "own_ring_i_weight", "opp_ring_i_weight", "own_ring_m_weight",
    "opp_ring_m_weight", "own_ring_o_weight", "opp_ring_o_weight",
)
POLICY_FEATURE_NAMES = (
    "bias", "power_1", "power_2", "power_3", "power", "placement_ring_i",
    "placement_ring_m", "placement_ring_o", "rotation_ring_i",
    "rotation_ring_m", "rotation_ring_o", "same_ring", "direction_cw",
    "direction_ccw", "settled_sector", "ply", "plies_to_tide", "score_diff",
    "same_power_left", "post_own_spoke_leads", "post_opp_spoke_leads",
    "post_tied_spokes", "post_own_spoke_margin", "immediate_own_points",
    "immediate_opp_points",
)

STATE_FIELDS = frozenset(
    {
        "protocol",
        "ruleset",
        "rings",
        "sectors",
        "player_color",
        "opponent_model_id",
        "opponent_model_sha256",
        "opponent_dataset_sha256",
        "opponent_node_budget",
        "opponent_search_width",
        "opponent_max_depth",
        "opponent_seed",
        "opponent_selection_profile",
        "opponent_root_temperature_milli",
        "opponent_root_rank_lapse_permille",
        "opponent_move_time_limit_ms",
        "turn",
        "result",
        "winner",
        "termination",
        "ply_count",
        "previous_action",
        "gold_score",
        "violet_score",
        "gold_inventory",
        "violet_inventory",
        "board",
        "tide_history",
        "legal_actions",
        "postgame_player_requests",
        "state_hash",
        "latest_record",
    }
)
INVENTORY_FIELDS = frozenset({"P1", "P2", "P3"})
BOARD_FIELDS = frozenset({"slot", "ring", "sector", "occupant", "power"})
TIDE_FIELDS = frozenset({"tide", "ply", "gold_points", "violet_points", "spokes"})
SPOKE_FIELDS = frozenset(
    {"sector", "gold_weight", "violet_weight", "point_owner"}
)
RECORD_FIELDS = frozenset(
    {
        "record",
        "actor",
        "color",
        "action",
        "placed_slot",
        "settled_slot",
        "state_hash_before",
        "state_hash_after",
        "tide",
    }
)
ERROR_FIELDS = frozenset({"code", "message"})


def other(color: str) -> str:
    """Return the opposing color without consulting packaged game code."""
    assert color in COLORS
    return "violet" if color == "gold" else "gold"


def slot_index(ring: str, sector: str) -> int:
    """Map one canonical ring-sector coordinate to the verifier board index."""
    assert ring in RINGS and sector in SECTORS
    return RINGS.index(ring) * len(SECTORS) + SECTORS.index(sector)


def rotate_sector(sector: str, direction: str) -> str:
    """Rotate one sector exactly one step under the public direction convention."""
    delta = 1 if direction == "CW" else -1
    return SECTORS[(SECTORS.index(sector) + delta) % len(SECTORS)]


@dataclass(frozen=True, order=True)
class Action:
    """One canonical power, placement slot, ring, and direction action."""

    power: int
    placement_ring: str
    placement_sector: str
    rotation_ring: str
    direction: str

    @property
    def placement_slot(self) -> str:
        """Return the pre-rotation placement coordinate."""
        return f"{self.placement_ring}{self.placement_sector}"

    @property
    def settled_slot(self) -> str:
        """Return the placed stone's coordinate after the selected rotation."""
        sector = self.placement_sector
        if self.placement_ring == self.rotation_ring:
            sector = rotate_sector(sector, self.direction)
        return f"{self.placement_ring}{sector}"

    def text(self) -> str:
        """Format the sole canonical public action representation."""
        return (
            f"P{self.power} {self.placement_slot} "
            f"{self.rotation_ring} {self.direction}"
        )


@dataclass(frozen=True)
class Stone:
    """One retained colored weighted stone in its current board cell."""

    stone_id: str
    owner: str
    power: int


@dataclass(frozen=True)
class Move:
    """One native accepted placement used by canonical hashing."""

    stone_id: str
    owner: str
    action: Action
    placed_slot: str
    settled_slot: str


@dataclass(frozen=True)
class Spoke:
    """One independently totaled sector in a tide event."""

    sector: str
    gold_weight: int
    violet_weight: int
    point_owner: str | None


@dataclass(frozen=True)
class Tide:
    """One immutable six-spoke scoring event."""

    tide: int
    ply: int
    gold_points: int
    violet_points: int
    spokes: tuple[Spoke, ...]


@dataclass(frozen=True)
class State:
    """The native hashed Tidevault state, excluding resignation overlay fields."""

    turn: str = "gold"
    ply: int = 0
    gold_score: int = 0
    violet_score: int = 0
    gold_inventory: tuple[int, int, int] = (3, 3, 3)
    violet_inventory: tuple[int, int, int] = (3, 3, 3)
    board: tuple[Stone | None, ...] = (None,) * len(SLOTS)
    moves: tuple[Move, ...] = ()
    tides: tuple[Tide, ...] = ()
    result: str = "ongoing"
    winner: str | None = None
    termination: str | None = None


@dataclass(frozen=True)
class Replay:
    """The independently replayed native state plus possible resignation overlay."""

    native: State
    resigned: bool
    records: tuple[Mapping[str, Any], ...]
    previous_action: str | None

    @property
    def result(self) -> str:
        """Return the public result after applying resignation semantics."""
        return "violet_win" if self.resigned else self.native.result

    @property
    def winner(self) -> str | None:
        """Return the public winner after applying resignation semantics."""
        return "violet" if self.resigned else self.native.winner

    @property
    def termination(self) -> str | None:
        """Return public termination after applying resignation semantics."""
        return "resignation" if self.resigned else self.native.termination


def parse_action(text: str) -> Action:
    """Parse one action and reject every non-canonical spelling."""
    assert isinstance(text, str), text
    match = ACTION_RE.fullmatch(text)
    assert match is not None, text
    power, placement_ring, placement_sector, rotation_ring, direction = match.groups()
    action = Action(
        int(power), placement_ring, placement_sector, rotation_ring, direction
    )
    assert action.text() == text, text
    return action


def inventory_for(state: State, color: str) -> tuple[int, int, int]:
    """Read one color's immutable power inventory."""
    assert color in COLORS
    return state.gold_inventory if color == "gold" else state.violet_inventory


def legal_actions(state: State, actor: str | None = None) -> tuple[Action, ...]:
    """Generate every legal action in the frozen canonical order."""
    if state.result != "ongoing":
        return ()
    color = state.turn if actor is None else actor
    inventory = inventory_for(state, color)
    actions: list[Action] = []
    for power in POWERS:
        if inventory[power - 1] <= 0:
            continue
        for slot, stone in zip(SLOTS, state.board):
            if stone is not None:
                continue
            for rotation_ring in RINGS:
                for direction in DIRECTIONS:
                    actions.append(
                        Action(power, slot[0], slot[1], rotation_ring, direction)
                    )
    return tuple(actions)


def rotate_board(
    board: tuple[Stone | None, ...], ring: str, direction: str
) -> tuple[Stone | None, ...]:
    """Rotate all six cells of one selected ring exactly one sector."""
    rotated = list(board)
    for sector in SECTORS:
        source = slot_index(ring, sector)
        destination = slot_index(ring, rotate_sector(sector, direction))
        rotated[destination] = board[source]
    return tuple(rotated)


def score_tide(board: tuple[Stone | None, ...], tide_number: int, ply: int) -> Tide:
    """Compute one six-spoke tide solely from the post-rotation board."""
    spokes: list[Spoke] = []
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
        point_owner: str | None = None
        if gold_weight > violet_weight:
            point_owner = "gold"
        elif violet_weight > gold_weight:
            point_owner = "violet"
        spokes.append(Spoke(sector, gold_weight, violet_weight, point_owner))
    return Tide(
        tide_number,
        ply,
        sum(spoke.point_owner == "gold" for spoke in spokes),
        sum(spoke.point_owner == "violet" for spoke in spokes),
        tuple(spokes),
    )


def finish(state: State) -> State:
    """Adjudicate the fixed-length game while retaining the final actor's turn."""
    if state.gold_score > state.violet_score:
        result, winner = "gold_win", "gold"
    elif state.violet_score > state.gold_score:
        result, winner = "violet_win", "violet"
    else:
        result, winner = "draw", None
    return replace(state, result=result, winner=winner, termination="complete")


def apply_action(state: State, action: Action) -> State:
    """Apply placement, ring rotation, optional tide, and terminal order independently."""
    assert action in legal_actions(state), (state, action)
    owner = state.turn
    board = list(state.board)
    stone_id = f"S{state.ply + 1:02d}"
    board[slot_index(action.placement_ring, action.placement_sector)] = Stone(
        stone_id, owner, action.power
    )
    rotated = rotate_board(tuple(board), action.rotation_ring, action.direction)
    gold_inventory = list(state.gold_inventory)
    violet_inventory = list(state.violet_inventory)
    inventory = gold_inventory if owner == "gold" else violet_inventory
    inventory[action.power - 1] -= 1
    ply = state.ply + 1
    tides = state.tides
    gold_score = state.gold_score
    violet_score = state.violet_score
    if ply in TIDE_PLIES:
        tide = score_tide(rotated, len(tides) + 1, ply)
        tides += (tide,)
        gold_score += tide.gold_points
        violet_score += tide.violet_points
    placed = replace(
        state,
        ply=ply,
        gold_score=gold_score,
        violet_score=violet_score,
        gold_inventory=tuple(gold_inventory),
        violet_inventory=tuple(violet_inventory),
        board=rotated,
        moves=state.moves
        + (
            Move(
                stone_id,
                owner,
                action,
                action.placement_slot,
                action.settled_slot,
            ),
        ),
        tides=tides,
    )
    if ply == PLY_LIMIT:
        return finish(placed)
    return replace(placed, turn=other(owner))


def public_spoke(spoke: Spoke) -> dict[str, Any]:
    """Translate one independent spoke result to the exact public shape."""
    return {
        "sector": spoke.sector,
        "gold_weight": spoke.gold_weight,
        "violet_weight": spoke.violet_weight,
        "point_owner": spoke.point_owner,
    }


def public_tide(tide: Tide) -> dict[str, Any]:
    """Translate one independent tide result to the exact public shape."""
    return {
        "tide": tide.tide,
        "ply": tide.ply,
        "gold_points": tide.gold_points,
        "violet_points": tide.violet_points,
        "spokes": [public_spoke(spoke) for spoke in tide.spokes],
    }


def canonical_stone(stone: Stone | None) -> dict[str, Any] | None:
    """Translate one native cell into the compact canonical hash form."""
    return (
        None
        if stone is None
        else {"owner": stone.owner, "power": stone.power, "stone_id": stone.stone_id}
    )


def canonical_move(move: Move) -> dict[str, Any]:
    """Translate one independent native move into canonical hash evidence."""
    return {
        "action": move.action.text(),
        "owner": move.owner,
        "placed_slot": move.placed_slot,
        "settled_slot": move.settled_slot,
        "stone_id": move.stone_id,
    }


def canonical_state_object(state: State) -> dict[str, Any]:
    """Construct the frozen native hash object without result overlay fields."""
    return {
        "board": [canonical_stone(stone) for stone in state.board],
        "inventories": [list(state.gold_inventory), list(state.violet_inventory)],
        "moves": [canonical_move(move) for move in state.moves],
        "ply": state.ply,
        "ruleset": RULESET,
        "scores": [state.gold_score, state.violet_score],
        "tides": [public_tide(tide) for tide in state.tides],
        "turn": state.turn,
    }


def canonical_serialize(state: State) -> str:
    """Serialize native state as compact sorted-key ASCII JSON."""
    return json.dumps(
        canonical_state_object(state),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def state_hash(state: State) -> str:
    """Hash the exact native serialization with lowercase SHA-256."""
    return hashlib.sha256(canonical_serialize(state).encode("ascii")).hexdigest()


def run_arena(
    output_flag: str | None, *arguments: str, timeout: float = 8.0
) -> subprocess.CompletedProcess[str]:
    """Run one bounded root-owned public request without participant accounting."""
    command = ["/app/arena"]
    if output_flag is not None:
        command.append(output_flag)
    command.extend(arguments)
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    assert len(completed.stdout.encode("utf-8")) <= MAX_PUBLIC_BYTES
    return completed


def run_json(*arguments: str) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    """Run one JSON request and decode exactly one object."""
    completed = run_arena("--json", *arguments)
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        pytest.fail(
            f"arena returned invalid JSON: {error}\nrc={completed.returncode}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    assert isinstance(document, dict), document
    return completed, document


def run_raw_json(*fields: str) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    """Send one raw request to exercise root-only atomic rejection paths."""
    payload = ("\t".join(fields) + "\n").encode("ascii")
    assert 0 < len(payload) <= 8192
    return run_raw_payload(payload, ["raw-arena", *fields])


def run_raw_payload(
    payload: bytes, arguments: list[str] | None = None
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    """Send exact bytes to attest bounded socket framing and error responses."""
    assert payload and len(payload) <= 16384
    response = bytearray()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
        channel.settimeout(5.0)
        channel.connect("/run/arena/arena.sock")
        channel.sendall(payload)
        channel.shutdown(socket.SHUT_WR)
        while True:
            block = channel.recv(65536)
            if not block:
                break
            response.extend(block)
            assert len(response) <= MAX_PUBLIC_BYTES
    text = response.decode("ascii")
    document = json.loads(text)
    assert isinstance(document, dict), document
    return (
        subprocess.CompletedProcess(
            args=arguments or ["raw-arena-bytes"],
            returncode=0 if document.get("ok") is True else 1,
            stdout=text,
            stderr="",
        ),
        document,
    )


def require_hash(value: Any) -> None:
    """Require one non-placeholder lowercase SHA-256 string."""
    assert isinstance(value, str) and HASH_RE.fullmatch(value), value
    assert value != "0" * 64, value


def require_inventory(value: Any) -> None:
    """Validate one exact public power-inventory object."""
    assert isinstance(value, dict) and set(value) == INVENTORY_FIELDS, value
    for power in ("P1", "P2", "P3"):
        assert type(value[power]) is int and 0 <= value[power] <= 3, value


def require_tide(value: Any, index: int | None = None) -> None:
    """Validate one exact tide event and its six ordered spoke totals."""
    assert isinstance(value, dict) and set(value) == TIDE_FIELDS, value
    assert type(value["tide"]) is int, value
    assert 1 <= value["tide"] <= len(TIDE_PLIES), value
    if index is not None:
        assert value["tide"] == index, value
    assert value["ply"] == TIDE_PLIES[value["tide"] - 1], value
    assert type(value["gold_points"]) is int, value
    assert type(value["violet_points"]) is int, value
    assert isinstance(value["spokes"], list) and len(value["spokes"]) == 6, value
    for sector, spoke in zip(SECTORS, value["spokes"]):
        assert isinstance(spoke, dict) and set(spoke) == SPOKE_FIELDS, spoke
        assert spoke["sector"] == sector, spoke
        assert type(spoke["gold_weight"]) is int and spoke["gold_weight"] >= 0
        assert type(spoke["violet_weight"]) is int and spoke["violet_weight"] >= 0
        assert spoke["point_owner"] in {None, "gold", "violet"}, spoke
        expected: str | None = None
        if spoke["gold_weight"] > spoke["violet_weight"]:
            expected = "gold"
        elif spoke["violet_weight"] > spoke["gold_weight"]:
            expected = "violet"
        assert spoke["point_owner"] == expected, spoke
    assert value["gold_points"] == sum(
        spoke["point_owner"] == "gold" for spoke in value["spokes"]
    )
    assert value["violet_points"] == sum(
        spoke["point_owner"] == "violet" for spoke in value["spokes"]
    )


def require_record(value: Any, index: int | None = None) -> None:
    """Validate one exact placement or resignation transcript record."""
    assert isinstance(value, dict) and set(value) == RECORD_FIELDS, value
    assert type(value["record"]) is int and value["record"] > 0, value
    if index is not None:
        assert value["record"] == index, value
    assert value["actor"] in {"player", "opponent"}, value
    assert value["color"] in COLORS, value
    require_hash(value["state_hash_before"])
    require_hash(value["state_hash_after"])
    if value["action"] is None:
        assert value["actor"] == "player" and value["color"] == "gold", value
        assert value["placed_slot"] is None and value["settled_slot"] is None
        assert value["tide"] is None, value
        assert value["state_hash_before"] == value["state_hash_after"], value
    else:
        action = parse_action(value["action"])
        assert value["placed_slot"] == action.placement_slot, value
        assert value["settled_slot"] == action.settled_slot, value
        if value["tide"] is not None:
            require_tide(value["tide"])


def require_state(value: Any) -> None:
    """Validate every exact top-level and nested public state field."""
    assert isinstance(value, dict) and set(value) == STATE_FIELDS, value
    assert value["protocol"] == PROTOCOL, value
    assert value["ruleset"] == RULESET, value
    assert value["rings"] == list(RINGS), value
    assert value["sectors"] == list(SECTORS), value
    assert value["player_color"] == "gold", value
    assert isinstance(value["opponent_model_id"], str), value
    assert MODEL_RE.fullmatch(value["opponent_model_id"]), value
    assert "calibrat" not in value["opponent_model_id"], value
    require_hash(value["opponent_model_sha256"])
    require_hash(value["opponent_dataset_sha256"])
    for field in (
        "opponent_node_budget",
        "opponent_search_width",
        "opponent_max_depth",
        "opponent_seed",
        "opponent_move_time_limit_ms",
    ):
        assert type(value[field]) is int and value[field] > 0, (field, value)
    assert value["opponent_selection_profile"] == "beam-rank-lapse-v1", value
    assert value["opponent_root_temperature_milli"] == 0, value
    assert type(value["opponent_root_rank_lapse_permille"]) is int, value
    assert 0 <= value["opponent_root_rank_lapse_permille"] <= 1000, value
    assert value["turn"] in COLORS, value
    assert value["result"] in {"ongoing", "gold_win", "violet_win", "draw"}, value
    assert value["winner"] in {None, "gold", "violet"}, value
    assert value["termination"] in {None, "complete", "resignation"}, value
    assert type(value["ply_count"]) is int and 0 <= value["ply_count"] <= 18, value
    if value["previous_action"] is not None:
        parse_action(value["previous_action"])
    for field in ("gold_score", "violet_score", "postgame_player_requests"):
        assert type(value[field]) is int and value[field] >= 0, (field, value)
    require_inventory(value["gold_inventory"])
    require_inventory(value["violet_inventory"])
    assert isinstance(value["board"], list) and len(value["board"]) == 18, value
    for slot, cell in zip(SLOTS, value["board"]):
        assert isinstance(cell, dict) and set(cell) == BOARD_FIELDS, cell
        assert cell["slot"] == slot and cell["ring"] == slot[0], cell
        assert cell["sector"] == slot[1], cell
        assert cell["occupant"] in {None, "gold", "violet"}, cell
        assert cell["power"] in {None, 1, 2, 3}, cell
        assert (cell["occupant"] is None) == (cell["power"] is None), cell
    assert isinstance(value["tide_history"], list), value
    expected_tides = sum(ply <= value["ply_count"] for ply in TIDE_PLIES)
    assert len(value["tide_history"]) == expected_tides, value
    for index, tide in enumerate(value["tide_history"], start=1):
        require_tide(tide, index)
    assert isinstance(value["legal_actions"], list), value
    for action in value["legal_actions"]:
        parse_action(action)
    require_hash(value["state_hash"])
    if value["latest_record"] is not None:
        require_record(value["latest_record"])
    if value["result"] == "ongoing":
        assert value["winner"] is None and value["termination"] is None, value
    else:
        assert value["legal_actions"] == [], value


def expected_inventory(values: tuple[int, int, int]) -> dict[str, int]:
    """Translate native inventory entries to their exact public keys."""
    return {f"P{power}": values[power - 1] for power in POWERS}


def expected_board(values: Sequence[Stone | None]) -> list[dict[str, Any]]:
    """Translate independent board cells to the ordered public board list."""
    return [
        {
            "slot": slot,
            "ring": slot[0],
            "sector": slot[1],
            "occupant": None if stone is None else stone.owner,
            "power": None if stone is None else stone.power,
        }
        for slot, stone in zip(SLOTS, values)
    ]


def replay_records(records: Sequence[Mapping[str, Any]]) -> Replay:
    """Replay all trusted actions without importing or invoking packaged rules."""
    state = State()
    resigned = False
    previous_action: str | None = None
    for index, record in enumerate(records, start=1):
        require_record(record, index)
        assert not resigned and state.result == "ongoing", (state, record)
        assert record["state_hash_before"] == state_hash(state), (state, record)
        expected_actor = "player" if state.turn == "gold" else "opponent"
        assert record["actor"] == expected_actor and record["color"] == state.turn
        if record["action"] is None:
            assert state.turn == "gold" and index == len(records), records
            assert record["state_hash_after"] == state_hash(state), record
            resigned = True
            continue
        action = parse_action(record["action"])
        assert action in legal_actions(state), (state, action)
        before_tides = len(state.tides)
        next_state = apply_action(state, action)
        assert record["placed_slot"] == action.placement_slot, record
        assert record["settled_slot"] == action.settled_slot, record
        expected_tide = (
            public_tide(next_state.tides[-1])
            if len(next_state.tides) > before_tides
            else None
        )
        assert record["tide"] == expected_tide, (record, expected_tide)
        assert record["state_hash_after"] == state_hash(next_state), record
        previous_action = action.text()
        state = next_state
    return Replay(state, resigned, tuple(records), previous_action)


def require_document_matches_replay(
    document: Mapping[str, Any], replay: Replay
) -> None:
    """Compare every replay-derived field with the trusted public snapshot."""
    state = replay.native
    assert document["turn"] == state.turn
    assert document["result"] == replay.result
    assert document["winner"] == replay.winner
    assert document["termination"] == replay.termination
    assert document["ply_count"] == state.ply
    assert document["previous_action"] == replay.previous_action
    assert document["gold_score"] == state.gold_score
    assert document["violet_score"] == state.violet_score
    assert document["gold_inventory"] == expected_inventory(state.gold_inventory)
    assert document["violet_inventory"] == expected_inventory(state.violet_inventory)
    assert document["board"] == expected_board(state.board)
    assert document["tide_history"] == [
        public_tide(tide) for tide in state.tides
    ]
    expected_legal = [] if replay.result != "ongoing" else [
        action.text() for action in legal_actions(state)
    ]
    assert document["legal_actions"] == expected_legal
    assert document["state_hash"] == state_hash(state)
    assert document["latest_record"] == (replay.records[-1] if replay.records else None)


@dataclass(frozen=True)
class TrustedSnapshot:
    """One authoritative transcript fetch and independent replay shared by tests."""

    document: Mapping[str, Any]
    records: tuple[Mapping[str, Any], ...]
    replay: Replay


@pytest.fixture(scope="session")
def trusted_snapshot() -> TrustedSnapshot:
    """Fetch, schema-check, and independently replay the final transcript once."""
    completed, document = run_json("transcript")
    assert completed.returncode == 0 and completed.stderr == "", completed
    assert set(document) == {"ok", "actions"} | STATE_FIELDS, document
    assert document["ok"] is True, document
    view = {key: document[key] for key in STATE_FIELDS}
    require_state(view)
    assert isinstance(document["actions"], list), document
    records = tuple(document["actions"])
    replay = replay_records(records)
    require_document_matches_replay(view, replay)
    return TrustedSnapshot(document, records, replay)


def state_view(document: Mapping[str, Any]) -> dict[str, Any]:
    """Select exact state fields from one success envelope."""
    return {key: document[key] for key in STATE_FIELDS}


def parse_wire(document: str) -> tuple[str, str | None]:
    """Parse a bounded Tidevault wire envelope."""
    encoded = document.encode("utf-8")
    assert len(encoded) <= MAX_PUBLIC_BYTES
    encoded.decode("ascii")
    lines = document.splitlines()
    assert lines and lines[0] == "TIDEVAULT_WIRE_V1", lines[:4]
    assert lines[-1] == "END", lines[-4:]
    if len(lines) == 3 and lines[1] == "READY\t1":
        return "READY", None
    assert len(lines) == 4 and lines[1] in {"OK", "FAIL"}, lines
    prefix, separator, payload = lines[2].partition("\t")
    assert prefix == "JSON" and separator == "\t" and payload, lines
    assert "\n" not in payload and "\r" not in payload
    return lines[1], payload


@dataclass(frozen=True)
class LinearCheckpoint:
    """A strictly decoded first-party checkpoint with no packaged-code dependency."""

    model_id: str
    dataset_sha256: str
    epoch: int
    seed: int
    training_games: int
    training_samples: int
    value_feature_names: tuple[str, ...]
    policy_feature_names: tuple[str, ...]
    value_weights: tuple[int, ...]
    policy_weights: tuple[int, ...]

    def value(self, state: State, actor: str) -> int:
        """Evaluate one position through independent named feature extraction."""
        if state.result != "ongoing":
            margin = (
                state.gold_score - state.violet_score
                if actor == "gold"
                else state.violet_score - state.gold_score
            )
            if state.winner == actor:
                return 1_000_000_000 + 1_000_000 * margin
            if state.winner is None:
                return 0
            return -1_000_000_000 + 1_000_000 * margin
        features = feature_vector(self.value_feature_names, state, None, actor)
        return sum(
            weight * feature
            for weight, feature in zip(self.value_weights, features)
        )

    def policy(self, state: State, action: Action, actor: str | None = None) -> int:
        """Evaluate one action through independent named feature extraction."""
        color = state.turn if actor is None else actor
        features = feature_vector(self.policy_feature_names, state, action, color)
        return sum(
            weight * feature
            for weight, feature in zip(self.policy_weights, features)
        )


@dataclass(frozen=True)
class FrozenSettings:
    """The protected runtime tuple parsed as inert shell assignments."""

    model_path: Path
    model_id: str
    model_sha256: str
    dataset_sha256: str
    node_budget: int
    width: int
    max_depth: int
    seed: int
    selection_profile: str
    root_temperature_milli: int
    root_rank_lapse_permille: int
    move_time_limit_ms: int


def current_spoke_totals(state: State, actor: str) -> tuple[list[int], list[int]]:
    """Return own and opposing weights on each current spoke."""
    own: list[int] = []
    opponent: list[int] = []
    for sector in SECTORS:
        own_weight = 0
        opponent_weight = 0
        for ring in RINGS:
            stone = state.board[slot_index(ring, sector)]
            if stone is None:
                continue
            if stone.owner == actor:
                own_weight += stone.power
            else:
                opponent_weight += stone.power
        own.append(own_weight)
        opponent.append(opponent_weight)
    return own, opponent


def plies_to_next_tide(ply: int) -> int:
    """Return the exact distance to the next half-full or full-board tide."""
    return next((tide_ply - ply for tide_ply in TIDE_PLIES if tide_ply > ply), 0)


def named_features(state: State, action: Action | None, actor: str) -> dict[str, int]:
    """Compute the complete Tidevault feature vocabulary independently by name."""
    own_inventory = inventory_for(state, actor)
    opponent_inventory = inventory_for(state, other(actor))
    sign = 1 if actor == "gold" else -1
    own_spokes, opponent_spokes = current_spoke_totals(state, actor)
    values: dict[str, int] = {
        "bias": 1,
        "score_diff": sign * (state.gold_score - state.violet_score),
        "ply": state.ply,
        "tides_completed": len(state.tides),
        "plies_to_tide": plies_to_next_tide(state.ply),
        "own_p1_left": own_inventory[0],
        "own_p2_left": own_inventory[1],
        "own_p3_left": own_inventory[2],
        "opp_p1_left": opponent_inventory[0],
        "opp_p2_left": opponent_inventory[1],
        "opp_p3_left": opponent_inventory[2],
        "empty_slots": sum(stone is None for stone in state.board),
        "own_board_weight": sum(
            stone.power for stone in state.board if stone is not None and stone.owner == actor
        ),
        "opp_board_weight": sum(
            stone.power
            for stone in state.board
            if stone is not None and stone.owner == other(actor)
        ),
        "own_spoke_leads": sum(a > b for a, b in zip(own_spokes, opponent_spokes)),
        "opp_spoke_leads": sum(b > a for a, b in zip(own_spokes, opponent_spokes)),
        "tied_spokes": sum(a == b for a, b in zip(own_spokes, opponent_spokes)),
        "own_spoke_margin": sum(a - b for a, b in zip(own_spokes, opponent_spokes)),
        "own_max_spoke": max(
            (0, *(a - b for a, b in zip(own_spokes, opponent_spokes)))
        ),
        "opp_max_spoke": max(
            (0, *(b - a for a, b in zip(own_spokes, opponent_spokes)))
        ),
    }
    for ring in RINGS:
        values[f"own_ring_{ring.lower()}_weight"] = sum(
            stone.power
            for sector in SECTORS
            if (stone := state.board[slot_index(ring, sector)]) is not None
            and stone.owner == actor
        )
        values[f"opp_ring_{ring.lower()}_weight"] = sum(
            stone.power
            for sector in SECTORS
            if (stone := state.board[slot_index(ring, sector)]) is not None
            and stone.owner == other(actor)
        )
    if action is not None:
        child = apply_action(state, action)
        child_own, child_opponent = current_spoke_totals(child, actor)
        before_tides = len(state.tides)
        tide = child.tides[-1] if len(child.tides) > before_tides else None
        values.update(
            {
                "power_1": int(action.power == 1),
                "power_2": int(action.power == 2),
                "power_3": int(action.power == 3),
                "power": action.power,
                "placement_ring_i": int(action.placement_ring == "I"),
                "placement_ring_m": int(action.placement_ring == "M"),
                "placement_ring_o": int(action.placement_ring == "O"),
                "rotation_ring_i": int(action.rotation_ring == "I"),
                "rotation_ring_m": int(action.rotation_ring == "M"),
                "rotation_ring_o": int(action.rotation_ring == "O"),
                "same_ring": int(action.placement_ring == action.rotation_ring),
                "direction_cw": int(action.direction == "CW"),
                "direction_ccw": int(action.direction == "CCW"),
                "settled_sector": SECTORS.index(action.settled_slot[1]),
                "post_own_spoke_leads": sum(
                    a > b for a, b in zip(child_own, child_opponent)
                ),
                "post_opp_spoke_leads": sum(
                    b > a for a, b in zip(child_own, child_opponent)
                ),
                "post_tied_spokes": sum(
                    a == b for a, b in zip(child_own, child_opponent)
                ),
                "post_own_spoke_margin": sum(
                    a - b for a, b in zip(child_own, child_opponent)
                ),
                "immediate_own_points": 0
                if tide is None
                else tide.gold_points if actor == "gold" else tide.violet_points,
                "immediate_opp_points": 0
                if tide is None
                else tide.violet_points if actor == "gold" else tide.gold_points,
                "same_power_left": own_inventory[action.power - 1],
            }
        )
    return values


def feature_vector(
    names: Sequence[str], state: State, action: Action | None, actor: str
) -> tuple[int, ...]:
    """Resolve every checkpoint feature name through the independent vocabulary."""
    values = named_features(state, action, actor)
    missing = [name for name in names if name not in values]
    assert not missing, f"unimplemented independent features: {missing}"
    return tuple(values[name] for name in names)


def load_checkpoint_independently(path: Path) -> LinearCheckpoint:
    """Strictly decode one canonical checkpoint without packaged model code."""
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and not path.is_symlink(), path
    assert info.st_uid == 0 and not (info.st_mode & 0o077), oct(info.st_mode)
    raw = path.read_bytes()
    value = json.loads(raw.decode("ascii"))
    expected_keys = {
        "format", "model_id", "dataset_sha256", "epoch", "seed",
        "training_games", "training_samples", "value_feature_names",
        "policy_feature_names", "value_weights", "policy_weights", "weight_scale",
    }
    assert isinstance(value, dict) and set(value) == expected_keys, value
    assert value["format"] == "tidevault-linear-v1", value
    assert value["weight_scale"] == 100_000, value
    assert value["value_feature_names"] == list(VALUE_FEATURE_NAMES), value
    assert value["policy_feature_names"] == list(POLICY_FEATURE_NAMES), value
    model = LinearCheckpoint(
        model_id=value["model_id"],
        dataset_sha256=value["dataset_sha256"],
        epoch=value["epoch"],
        seed=value["seed"],
        training_games=value["training_games"],
        training_samples=value["training_samples"],
        value_feature_names=tuple(value["value_feature_names"]),
        policy_feature_names=tuple(value["policy_feature_names"]),
        value_weights=tuple(value["value_weights"]),
        policy_weights=tuple(value["policy_weights"]),
    )
    assert MODEL_RE.fullmatch(model.model_id), model
    require_hash(model.dataset_sha256)
    assert type(model.epoch) is int and model.epoch > 0, model
    assert type(model.seed) is int and model.seed > 0, model
    assert type(model.training_games) is int and model.training_games > 0, model
    assert type(model.training_samples) is int and model.training_samples > 0, model
    assert len(model.value_weights) == len(model.value_feature_names), model
    assert len(model.policy_weights) == len(model.policy_feature_names), model
    assert all(type(weight) is int for weight in model.value_weights), model
    assert all(type(weight) is int for weight in model.policy_weights), model
    canonical = (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("ascii")
    assert raw == canonical, path
    return model


def parse_inert_assignments(path: Path) -> dict[str, str]:
    """Parse a strict assignment-only config without executing shell content."""
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and not path.is_symlink(), path
    assert info.st_uid == 0 and not (info.st_mode & 0o077), oct(info.st_mode)
    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", line)
        assert match is not None, (line_number, raw)
        parts = shlex.split(match.group(2), posix=True)
        assert len(parts) == 1 and match.group(1) not in values, raw
        values[match.group(1)] = parts[0]
    return values


def load_settings_independently() -> tuple[FrozenSettings, LinearCheckpoint]:
    """Attest protected config, checkpoint bytes, and tuple relationships."""
    raw = parse_inert_assignments(Path("/opt/arena-private/difficulty_knobs.conf"))
    expected_keys = {
        "OPPONENT_MODEL_FILE", "OPPONENT_MODEL_ID", "OPPONENT_MODEL_SHA256",
        "OPPONENT_DATASET_SHA256", "OPPONENT_NODE_BUDGET",
        "OPPONENT_SEARCH_WIDTH", "OPPONENT_MAX_DEPTH", "OPPONENT_SEED",
        "OPPONENT_SELECTION_PROFILE", "OPPONENT_ROOT_TEMPERATURE_MILLI",
        "OPPONENT_ROOT_RANK_LAPSE_PERMILLE", "OPPONENT_MOVE_TIME_LIMIT_MS",
    }
    assert set(raw) == expected_keys, raw
    settings = FrozenSettings(
        Path(raw["OPPONENT_MODEL_FILE"]), raw["OPPONENT_MODEL_ID"],
        raw["OPPONENT_MODEL_SHA256"], raw["OPPONENT_DATASET_SHA256"],
        int(raw["OPPONENT_NODE_BUDGET"]), int(raw["OPPONENT_SEARCH_WIDTH"]),
        int(raw["OPPONENT_MAX_DEPTH"]), int(raw["OPPONENT_SEED"]),
        raw["OPPONENT_SELECTION_PROFILE"],
        int(raw["OPPONENT_ROOT_TEMPERATURE_MILLI"]),
        int(raw["OPPONENT_ROOT_RANK_LAPSE_PERMILLE"]),
        int(raw["OPPONENT_MOVE_TIME_LIMIT_MS"]),
    )
    assert settings.model_path.is_absolute(), settings
    require_hash(settings.model_sha256)
    require_hash(settings.dataset_sha256)
    assert settings.selection_profile == "beam-rank-lapse-v1", settings
    assert settings.node_budget > 0 and settings.width > 0, settings
    assert 0 < settings.max_depth <= PLY_LIMIT, settings
    assert settings.seed > 0 and settings.move_time_limit_ms > 0, settings
    assert settings.root_temperature_milli == 0, settings
    assert 0 <= settings.root_rank_lapse_permille <= 1000, settings
    model = load_checkpoint_independently(settings.model_path)
    assert hashlib.sha256(settings.model_path.read_bytes()).hexdigest() == settings.model_sha256
    assert model.model_id == settings.model_id, (model, settings)
    assert model.dataset_sha256 == settings.dataset_sha256, (model, settings)
    return settings, model


@dataclass(frozen=True)
class SearchConfig:
    """The independently enforced deterministic beam-search controls."""

    node_budget: int
    width: int
    max_depth: int
    seed: int
    selection_profile: str
    root_rank_lapse_permille: int
    root_temperature_milli: int


@dataclass(frozen=True)
class RankedChoice:
    """One completed root candidate and its root-perspective minimax value."""

    action: Action
    score: int


@dataclass(frozen=True)
class SearchResult:
    """Independent selected action and completed-iteration audit evidence."""

    action: Action
    score: int
    completed_depth: int
    nodes: int
    selected_rank: int
    ranked: tuple[RankedChoice, ...]


class BudgetExhausted(Exception):
    """Abort an incomplete iterative-deepening pass at the exact node ceiling."""


class SearchContext:
    """Hold the monotonic node counter across depth iterations."""

    def __init__(
        self, model: LinearCheckpoint, config: SearchConfig, root_actor: str
    ) -> None:
        self.model = model
        self.config = config
        self.root_actor = root_actor
        self.nodes = 0

    def visit(self) -> None:
        """Count one applied child or reject at the exact budget."""
        if self.nodes >= self.config.node_budget:
            raise BudgetExhausted
        self.nodes += 1


def digest_tiebreak(seed: int, digest: str, purpose: str, action: Action) -> int:
    """Generate the frozen unsigned 64-bit SHA tie key."""
    payload = f"{seed}|{digest}|{purpose}|{action.text()}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def ordered_search_actions(
    state: State, model: LinearCheckpoint, config: SearchConfig, purpose: str
) -> tuple[Action, ...]:
    """Take the top-width policy beam with deterministic digest ties."""
    digest = state_hash(state)
    return tuple(
        sorted(
            legal_actions(state),
            key=lambda action: (
                -model.policy(state, action),
                digest_tiebreak(config.seed, digest, purpose, action),
                action.text(),
            ),
        )[: config.width]
    )


def independent_minimax(state: State, depth: int, context: SearchContext) -> int:
    """Evaluate one beam-bounded subtree from the fixed root perspective."""
    if state.result != "ongoing" or depth == 0:
        return context.model.value(state, context.root_actor)
    actions = ordered_search_actions(state, context.model, context.config, f"d{depth}")
    maximizing = state.turn == context.root_actor
    best: int | None = None
    for action in actions:
        context.visit()
        score = independent_minimax(apply_action(state, action), depth - 1, context)
        if best is None or (maximizing and score > best) or (
            not maximizing and score < best
        ):
            best = score
    assert best is not None
    return best


def root_iteration(
    state: State, depth: int, context: SearchContext
) -> tuple[RankedChoice, ...]:
    """Complete one depth iteration or raise before publishing partial values."""
    actions = ordered_search_actions(state, context.model, context.config, "root-order")
    values: list[RankedChoice] = []
    for action in actions:
        context.visit()
        values.append(
            RankedChoice(
                action,
                independent_minimax(apply_action(state, action), depth - 1, context),
            )
        )
    digest = state_hash(state)
    values.sort(
        key=lambda item: (
            -item.score,
            digest_tiebreak(context.config.seed, digest, f"root-d{depth}", item.action),
            item.action.text(),
        )
    )
    return tuple(values)


def lapse_rank(state: State, config: SearchConfig, ranked_count: int) -> int:
    """Select rank one only on the documented deterministic weakening draw."""
    if ranked_count < 2 or config.root_rank_lapse_permille == 0:
        return 0
    payload = f"{config.seed}|{state_hash(state)}|rank-lapse".encode("ascii")
    draw = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % 1000
    return 1 if draw < config.root_rank_lapse_permille else 0


def analyze_independently(
    state: State, model: LinearCheckpoint, config: SearchConfig
) -> SearchResult:
    """Run iterative deepening and discard a budget-cut final iteration."""
    assert state.result == "ongoing" and legal_actions(state), state
    context = SearchContext(model, config, state.turn)
    completed: tuple[RankedChoice, ...] = ()
    completed_depth = 0
    for depth in range(1, min(config.max_depth, PLY_LIMIT - state.ply) + 1):
        try:
            candidate = root_iteration(state, depth, context)
        except BudgetExhausted:
            break
        completed = candidate
        completed_depth = depth
    if not completed:
        fallback = ordered_search_actions(state, model, config, "fallback")[0]
        completed = (RankedChoice(fallback, model.policy(state, fallback)),)
    selected_rank = lapse_rank(state, config, len(completed))
    selected = completed[selected_rank]
    return SearchResult(
        selected.action,
        selected.score,
        completed_depth,
        context.nodes,
        selected_rank,
        completed,
    )


def settings_search_config(settings: FrozenSettings) -> SearchConfig:
    """Translate protected assignments to independent search controls."""
    return SearchConfig(
        settings.node_budget,
        settings.width,
        settings.max_depth,
        settings.seed,
        settings.selection_profile,
        settings.root_rank_lapse_permille,
        settings.root_temperature_milli,
    )


def regenerate_violet_actions(
    records: Sequence[Mapping[str, Any]],
    model: LinearCheckpoint,
    config: SearchConfig,
) -> tuple[SearchResult, ...]:
    """Recompute every recorded Violet decision from its pre-action state."""
    state = State()
    results: list[SearchResult] = []
    for record in records:
        if record["action"] is None:
            break
        action = parse_action(record["action"])
        if state.turn == "violet":
            search = analyze_independently(state, model, config)
            assert search.action == action, (state, search, record)
            results.append(search)
        state = apply_action(state, action)
    return tuple(results)


@pytest.fixture(scope="session")
def protected_assets() -> tuple[FrozenSettings, LinearCheckpoint]:
    """Load protected settings and checkpoint once through independent parsers."""
    return load_settings_independently()


def require_rejection(
    completed: subprocess.CompletedProcess[str],
    document: Mapping[str, Any],
    expected_state: Mapping[str, Any],
    expected_code: str | None = None,
) -> None:
    """Validate a rejection envelope and its unchanged embedded state."""
    assert completed.returncode != 0 and completed.stderr == "", completed
    assert set(document) == {"ok", "error", "state"}, document
    assert document["ok"] is False, document
    assert isinstance(document["error"], dict), document
    assert set(document["error"]) == ERROR_FIELDS, document
    if expected_code is not None:
        assert document["error"]["code"] == expected_code, document
    assert isinstance(document["error"]["message"], str), document
    assert 0 < len(document["error"]["message"]) <= 240, document
    require_state(document["state"])
    assert document["state"] == expected_state, document


def test_independent_rule_hash_and_tide_vectors() -> None:
    """Independent vectors freeze action order, rotations, tide scoring, and hashing."""
    opening = State()
    assert len(legal_actions(opening)) == 324
    assert legal_actions(opening)[0].text() == "P1 IA I CW"
    assert legal_actions(opening)[-1].text() == "P3 OF O CCW"
    assert rotate_sector("A", "CW") == "B" and rotate_sector("A", "CCW") == "F"
    assert state_hash(opening) == (
        "ac0ab73579f47a82c3b149c189260055590a100c35211afffe71fd8e9329ca97"
    )
    state = opening
    for token in (
        "P3 IA I CW", "P2 OA O CCW", "P1 MA M CW",
        "P1 IC O CW", "P2 OC I CCW", "P3 MC M CCW",
        "P1 IC I CW", "P1 IA I CW", "P1 IA I CW",
    ):
        state = apply_action(state, parse_action(token))
    assert state.ply == 9 and len(state.tides) == 1
    tide = state.tides[0]
    assert tide.ply == 9 and tide.tide == 1
    assert (tide.gold_points, tide.violet_points) == (3, 3)
    assert (state.gold_score, state.violet_score) == (
        tide.gold_points, tide.violet_points
    )
    assert state_hash(state) == (
        "b9ce58572dd6d517e89a9d13a680a419f464d3d000955b2d5310e4dddb3c2989"
    )


def test_exact_public_json_schema_is_complete(trusted_snapshot: TrustedSnapshot) -> None:
    """Transcript exposes every documented exact field and nested object shape."""
    assert set(trusted_snapshot.document) == {"ok", "actions"} | STATE_FIELDS
    require_state(state_view(trusted_snapshot.document))
    assert trusted_snapshot.document["latest_record"] == (
        trusted_snapshot.document["actions"][-1]
        if trusted_snapshot.document["actions"]
        else None
    )


def test_transcript_records_are_sequential_and_canonical(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Every accepted placement or resignation has one sequential canonical record."""
    for index, record in enumerate(trusted_snapshot.records, start=1):
        require_record(record, index)
    native_count = sum(record["action"] is not None for record in trusted_snapshot.records)
    assert native_count == trusted_snapshot.replay.native.ply
    assert len(trusted_snapshot.records) == native_count + int(trusted_snapshot.replay.resigned)


def test_independent_replay_reconstructs_native_hash_chain(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Every record hash and final hash derive from independent canonical JSON."""
    replay = replay_records(trusted_snapshot.records)
    assert replay.native == trusted_snapshot.replay.native
    assert trusted_snapshot.document["state_hash"] == state_hash(replay.native)
    assert canonical_serialize(replay.native).isascii()


def test_tide_evidence_and_cumulative_scores_reconstruct_exactly(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Both periodic spoke totals independently sum to cumulative scores."""
    native = trusted_snapshot.replay.native
    assert native.gold_score == sum(tide.gold_points for tide in native.tides)
    assert native.violet_score == sum(tide.violet_points for tide in native.tides)
    assert trusted_snapshot.document["tide_history"] == [
        public_tide(tide) for tide in native.tides
    ]


def test_inventory_board_and_legal_order_reconstruct(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Inventories, retained stones, empty slots, and legal order all replay exactly."""
    native = trusted_snapshot.replay.native
    assert sum(native.gold_inventory) + sum(native.violet_inventory) == PLY_LIMIT - native.ply
    assert sum(stone is not None for stone in native.board) == native.ply
    assert sum(stone is None for stone in native.board) == PLY_LIMIT - native.ply
    expected = [] if trusted_snapshot.replay.result != "ongoing" else [
        action.text() for action in legal_actions(native)
    ]
    assert trusted_snapshot.document["legal_actions"] == expected


def test_terminal_and_resignation_semantics_match_replay(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Complete play and resignation preserve exact native and overlay semantics."""
    replay = trusted_snapshot.replay
    assert replay.result != "ongoing"
    if replay.resigned:
        assert replay.native.result == "ongoing"
        assert replay.winner == "violet" and replay.termination == "resignation"
        assert trusted_snapshot.records[-1]["action"] is None
    else:
        assert replay.native.ply == 18
        assert replay.native.termination == "complete"
        assert len(replay.native.tides) == 2
        assert replay.native.turn == trusted_snapshot.records[-1]["color"]


def test_status_and_transcript_are_identical_and_idempotent(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Repeated read-only requests expose one unchanged authoritative snapshot."""
    completed, status = run_json("status")
    assert completed.returncode == 0 and completed.stderr == ""
    assert set(status) == {"ok"} | STATE_FIELDS and status["ok"] is True
    assert state_view(status) == state_view(trusted_snapshot.document)
    again_completed, again = run_json("transcript")
    assert again_completed.returncode == 0 and again == trusted_snapshot.document


def test_json_ping_has_exact_readiness_shape() -> None:
    """JSON ping returns only the frozen boolean readiness envelope."""
    completed, document = run_json("ping")
    assert completed.returncode == 0 and completed.stderr == ""
    assert document == {"ok": True, "ready": True}


def test_wire_envelope_carries_the_same_compact_json(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Wire transcript and readiness are exact bounded envelopes over JSON."""
    completed = run_arena("--wire", "transcript")
    assert completed.returncode == 0 and completed.stderr == ""
    status, payload = parse_wire(completed.stdout)
    assert status == "OK" and payload is not None
    assert json.loads(payload) == trusted_snapshot.document
    assert payload == json.dumps(
        trusted_snapshot.document, ensure_ascii=True, separators=(",", ":")
    )
    ping = run_arena("--wire", "ping")
    assert ping.returncode == 0 and parse_wire(ping.stdout) == ("READY", None)


def test_human_surface_makes_complete_state_readable(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Human status prints settings, board, tides, terminal data, and state hash."""
    completed = run_arena(None, "status")
    assert completed.returncode == 0 and completed.stderr == ""
    for marker in (
        "TIDEVAULT HUMAN V1", "PROTOCOL:", "RULESET:", "PLAYER:",
        "SETTINGS:", "STATE:", "SCORES:", "INVENTORY:", "BOARD:",
        "TIDES (", "LATEST_RECORD:", "LEGAL_ACTIONS (",
        "POSTGAME_PLAYER_REQUESTS:", "STATE_HASH:",
    ):
        assert marker in completed.stdout, marker
    document = trusted_snapshot.document
    winner = document["winner"] if document["winner"] is not None else "-"
    termination = (
        document["termination"] if document["termination"] is not None else "-"
    )
    for literal in (
        f"PROTOCOL: {document['protocol']}",
        f"RULESET: {document['ruleset']}",
        f"PLAYER: {document['player_color']}",
        f"{document['opponent_model_id']} sha={document['opponent_model_sha256']}",
        f"dataset={document['opponent_dataset_sha256']}",
        f"nodes={document['opponent_node_budget']}",
        f"width={document['opponent_search_width']}",
        f"depth={document['opponent_max_depth']}",
        f"seed={document['opponent_seed']}",
        f"turn={document['turn']} result={document['result']} winner={winner} ",
        f"termination={termination} ply={document['ply_count']}/18",
        f"SCORES: Gold {document['gold_score']} Violet {document['violet_score']}",
        f"POSTGAME_PLAYER_REQUESTS: {document['postgame_player_requests']}",
        f"STATE_HASH: {document['state_hash']}",
    ):
        assert literal in completed.stdout, literal


def test_protected_checkpoint_and_public_tuple_attest(
    trusted_snapshot: TrustedSnapshot,
    protected_assets: tuple[FrozenSettings, LinearCheckpoint],
) -> None:
    """Protected assignments, checkpoint bytes, and every public knob agree."""
    settings, model = protected_assets
    document = trusted_snapshot.document
    assert document["opponent_model_id"] == settings.model_id == model.model_id
    assert document["opponent_model_sha256"] == settings.model_sha256
    assert document["opponent_dataset_sha256"] == settings.dataset_sha256
    assert document["opponent_node_budget"] == settings.node_budget
    assert document["opponent_search_width"] == settings.width
    assert document["opponent_max_depth"] == settings.max_depth
    assert document["opponent_seed"] == settings.seed
    assert document["opponent_selection_profile"] == settings.selection_profile
    assert document["opponent_root_temperature_milli"] == settings.root_temperature_milli
    assert document["opponent_root_rank_lapse_permille"] == settings.root_rank_lapse_permille
    assert document["opponent_move_time_limit_ms"] == settings.move_time_limit_ms
    protected_directory = Path("/opt/arena-private")
    directory_info = protected_directory.lstat()
    assert stat.S_ISDIR(directory_info.st_mode) and directory_info.st_uid == 0
    assert stat.S_IMODE(directory_info.st_mode) == 0o700
    for name in (
        "core.py", "model.py", "search.py", "referee.py", "mid.tvnn",
        "difficulty_knobs.conf", "healthcheck.sh",
    ):
        info = protected_directory.joinpath(name).lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_uid == 0, name
        assert stat.S_IMODE(info.st_mode) in {0o600, 0o700}, (name, oct(info.st_mode))
    client_info = Path("/app/arena").lstat()
    assert stat.S_ISREG(client_info.st_mode) and client_info.st_uid == 0
    assert stat.S_IMODE(client_info.st_mode) == 0o755
    socket_info = Path("/run/arena/arena.sock").lstat()
    assert stat.S_ISSOCK(socket_info.st_mode) and socket_info.st_uid == 0
    assert stat.S_IMODE(socket_info.st_mode) == 0o666


def test_every_violet_action_regenerates_from_checkpoint(
    trusted_snapshot: TrustedSnapshot,
    protected_assets: tuple[FrozenSettings, LinearCheckpoint],
) -> None:
    """Independent features and beam minimax reproduce every Violet choice."""
    settings, model = protected_assets
    searches = regenerate_violet_actions(
        trusted_snapshot.records, model, settings_search_config(settings)
    )
    expected_count = sum(
        record["color"] == "violet" for record in trusted_snapshot.records
    )
    assert len(searches) == expected_count
    for search in searches:
        assert search.nodes <= settings.node_budget
        assert 0 <= search.completed_depth <= settings.max_depth
        assert search.selected_rank in {0, 1}
        assert search.ranked and search.selected_rank < len(search.ranked)


def test_unknown_and_malformed_requests_reject_atomically(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Unknown commands and malformed framing fail without mutating final state."""
    before_completed, before = run_json("status")
    assert before_completed.returncode == 0
    rejected_completed, rejected = run_raw_json("not-a-tidevault-command")
    require_rejection(
        rejected_completed, rejected, state_view(before), "unknown_command"
    )
    for payload, code in (
        (b"status\x00\n", "bad_request"),
        (b"status\nsecond-line\n", "bad_request"),
        (b"x" * 8192 + b"\n", "request_too_large"),
    ):
        malformed_completed, malformed = run_raw_payload(payload)
        require_rejection(malformed_completed, malformed, state_view(before), code)
    after_completed, after = run_json("status")
    assert after_completed.returncode == 0 and after == before


def test_postgame_mutations_reject_and_player_count_stays_zero(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Root probes cannot alter terminal play or mask participant postgame requests."""
    before_completed, before = run_json("status")
    assert before_completed.returncode == 0
    expected = state_view(before)
    assert expected["result"] != "ongoing" and expected["postgame_player_requests"] == 0
    move_completed, move = run_json("move", "P0", "ZZ", "Z", "SIDEWAYS")
    require_rejection(move_completed, move, expected, "game_over")
    resign_completed, resign = run_json("resign")
    require_rejection(resign_completed, resign, expected, "game_over")
    after_completed, after = run_json("status")
    assert after_completed.returncode == 0 and state_view(after) == expected


def test_readme_freezes_complete_public_and_replay_contract(
    protected_assets: tuple[FrozenSettings, LinearCheckpoint],
) -> None:
    """README documents all commands, fields, rules, hashing, wire, and stop behavior."""
    readme = Path("/app/README.md").read_text(encoding="utf-8")
    lowered = readme.lower()
    for literal in (
        PROTOCOL, RULESET, "/app/arena status", "/app/arena move",
        "/app/arena transcript", "/app/arena resign", "TIDEVAULT_WIRE_V1",
        "CW", "CCW", "complete", "resignation",
    ):
        assert literal in readme, literal
    for field in sorted(STATE_FIELDS | RECORD_FIELDS | TIDE_FIELDS | SPOKE_FIELDS):
        assert field in readme, field
    for phrase in (
        "canonical legal-action order", "compact sorted-key ascii json", "sha-256",
        "one command at a time", "end your turn immediately",
        "postgame_player_requests", "full remaining horizon",
        "tides resolve after plies nine and eighteen",
        "half-full and full board snapshots",
    ):
        assert phrase in lowered, phrase
    assert "to_be_calibrated" not in lowered
    settings, _ = protected_assets
    for literal in (
        settings.model_id,
        settings.model_sha256,
        settings.dataset_sha256,
        f"{settings.node_budget:,}",
        f"width {settings.width}",
        f"seed {settings.seed}",
        f"{settings.move_time_limit_ms:,} ms",
        "root temperature exactly zero",
    ):
        assert literal in readme, literal


def test_final_state_is_a_genuine_gold_board_win(
    trusted_snapshot: TrustedSnapshot,
) -> None:
    """Passing alone requires a replayed native Gold victory without resignation."""
    replay = trusted_snapshot.replay
    assert not replay.resigned, trusted_snapshot.document
    assert replay.native.result == "gold_win", trusted_snapshot.document
    assert replay.native.winner == "gold", trusted_snapshot.document
    assert replay.native.termination == "complete", trusted_snapshot.document
    assert replay.native.ply == 18 and len(replay.native.tides) == 2
    assert replay.native.gold_score > replay.native.violet_score
    assert trusted_snapshot.document["postgame_player_requests"] == 0
