#!/usr/bin/env python3
"""Drive a strong Tidevault checkpoint through the sole public arena API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping, Sequence

import core
from model import checkpoint_sha256, load_checkpoint
from search import SearchConfig, analyze


ACTION_RE = re.compile(r"P[123] [IMO][A-F] [IMO] (?:CW|CCW)\Z")
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
STATE_FIELDS = {
    "protocol", "ruleset", "rings", "sectors", "player_color",
    "opponent_model_id", "opponent_model_sha256", "opponent_dataset_sha256",
    "opponent_node_budget", "opponent_search_width", "opponent_max_depth",
    "opponent_seed", "opponent_selection_profile",
    "opponent_root_temperature_milli", "opponent_root_rank_lapse_permille",
    "opponent_move_time_limit_ms", "turn", "result", "winner", "termination",
    "ply_count", "previous_action", "gold_score", "violet_score",
    "gold_inventory", "violet_inventory", "board", "tide_history",
    "legal_actions", "postgame_player_requests", "state_hash", "latest_record",
}
RECORD_FIELDS = {
    "record", "actor", "color", "action", "placed_slot", "settled_slot",
    "state_hash_before", "state_hash_after", "tide",
}


class OracleError(RuntimeError):
    """Report a fail-closed oracle attestation or play error."""


def require(condition: bool, message: str) -> None:
    """Raise unless one oracle invariant holds."""
    if not condition:
        raise OracleError(message)


def arena_request(client: Path, arguments: list[str], timeout: int) -> dict[str, Any]:
    """Issue one public command and parse its complete JSON response."""
    completed = subprocess.run(
        [str(client), "--json", *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    require(completed.returncode == 0, f"arena rejected {' '.join(arguments)}")
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise OracleError("arena returned malformed JSON") from error
    require(isinstance(document, dict), "arena JSON is not an object")
    return document


def inventory_object(values: tuple[int, int, int]) -> dict[str, int]:
    """Translate one solution-side inventory to the exact public object."""
    return {"P1": values[0], "P2": values[1], "P3": values[2]}


def spoke_object(spoke: core.SpokeScore) -> dict[str, object]:
    """Translate one solution-side spoke to the public evidence shape."""
    return {
        "sector": spoke.sector,
        "gold_weight": spoke.gold_weight,
        "violet_weight": spoke.violet_weight,
        "point_owner": spoke.point_owner,
    }


def tide_object(tide: core.Tide) -> dict[str, object]:
    """Translate one solution-side tide to the public evidence shape."""
    return {
        "tide": tide.tide,
        "ply": tide.ply,
        "gold_points": tide.gold_points,
        "violet_points": tide.violet_points,
        "spokes": [spoke_object(spoke) for spoke in tide.spokes],
    }


def board_objects(state: core.State) -> list[dict[str, object]]:
    """Translate the current solution-side board to the ordered public list."""
    values: list[dict[str, object]] = []
    for slot, stone in zip(core.SLOTS, state.board):
        values.append(
            {
                "slot": slot,
                "ring": slot[0],
                "sector": slot[1],
                "occupant": None if stone is None else stone.owner,
                "power": None if stone is None else stone.power,
            }
        )
    return values


def expected_tide(before: core.State, after: core.State) -> dict[str, object] | None:
    """Return the public tide appended by one native transition, if any."""
    return tide_object(after.tides[-1]) if len(after.tides) == len(before.tides) + 1 else None


def require_record_transition(
    record: Mapping[str, Any],
    before: core.State,
    after: core.State,
    action: core.Action,
    index: int,
) -> None:
    """Attest one public record against a solution-side native transition."""
    require(set(record) == RECORD_FIELDS, "record key set changed")
    require(record["record"] == index, "record sequence changed")
    require(record["actor"] == ("player" if before.turn == "gold" else "opponent"),
            "record actor changed")
    require(record["color"] == before.turn, "record color changed")
    require(record["action"] == core.format_action(action), "record action changed")
    move = after.moves[-1]
    require(record["placed_slot"] == move.placed_slot, "placed slot changed")
    require(record["settled_slot"] == move.settled_slot, "settled slot changed")
    require(record["state_hash_before"] == core.state_hash(before), "before hash changed")
    require(record["state_hash_after"] == core.state_hash(after), "after hash changed")
    require(record["tide"] == expected_tide(before, after), "record tide changed")


def replay_records(records: Sequence[Mapping[str, Any]]) -> tuple[core.State, bool]:
    """Reconstruct native play solely from the public transcript action strings."""
    state = core.initial_state()
    resigned = False
    for index, record in enumerate(records, start=1):
        require(isinstance(record, Mapping), "record is malformed")
        require(set(record) == RECORD_FIELDS, "record key set changed")
        if record.get("action") is None:
            require(index == len(records), "resignation is not final")
            require(state.turn == "gold" and state.result == "ongoing", "bad resignation")
            require(record["actor"] == "player" and record["color"] == "gold",
                    "resignation identity changed")
            require(record["placed_slot"] is None and record["settled_slot"] is None,
                    "resignation placement fields changed")
            require(record["tide"] is None, "resignation tide changed")
            digest = core.state_hash(state)
            require(record["state_hash_before"] == digest == record["state_hash_after"],
                    "resignation hash changed")
            resigned = True
            continue
        require(not resigned and state.result == "ongoing", "action follows terminal play")
        action = core.parse_action(record["action"])
        require(core.is_legal(state, action), "public transcript contains illegal action")
        next_state = core.apply_action(state, action)
        require_record_transition(record, state, next_state, action, index)
        state = next_state
    return state, resigned


def require_public_state(
    document: Mapping[str, Any],
    state: core.State,
    resigned: bool = False,
    include_actions: bool = False,
) -> None:
    """Compare every replay-derived public field to one complete arena response."""
    expected_keys = {"ok"} | STATE_FIELDS | ({"actions"} if include_actions else set())
    require(set(document) == expected_keys, "arena state key set changed")
    require(document["ok"] is True, "arena returned a rejection")
    require(document["protocol"] == core.PROTOCOL, "protocol changed")
    require(document["ruleset"] == core.RULESET, "ruleset changed")
    require(document["rings"] == list(core.RINGS), "ring order changed")
    require(document["sectors"] == list(core.SECTORS), "sector order changed")
    require(document["player_color"] == "gold", "player color changed")
    require(document["postgame_player_requests"] == 0, "postgame request recorded")
    result = "violet_win" if resigned else state.result
    winner = "violet" if resigned else state.winner
    termination = "resignation" if resigned else state.termination
    require(document["turn"] == state.turn, "public turn differs from replay")
    require(document["result"] == result, "public result differs from replay")
    require(document["winner"] == winner, "public winner differs from replay")
    require(document["termination"] == termination, "public termination differs from replay")
    require(document["ply_count"] == state.ply, "public ply differs from replay")
    previous = core.format_action(state.moves[-1].action) if state.moves else None
    require(document["previous_action"] == previous, "previous action differs from replay")
    require(document["gold_score"] == state.gold_score, "Gold score differs from replay")
    require(document["violet_score"] == state.violet_score, "Violet score differs from replay")
    require(document["gold_inventory"] == inventory_object(state.gold_inventory),
            "Gold inventory differs from replay")
    require(document["violet_inventory"] == inventory_object(state.violet_inventory),
            "Violet inventory differs from replay")
    require(document["board"] == board_objects(state), "board differs from replay")
    require(document["tide_history"] == [tide_object(tide) for tide in state.tides],
            "tide history differs from replay")
    legal = [] if resigned or state.terminal else [
        core.format_action(action) for action in core.legal_actions(state)
    ]
    require(document["legal_actions"] == legal, "legal action list differs from replay")
    require(document["state_hash"] == core.state_hash(state), "state hash differs from replay")


def play(options: argparse.Namespace) -> None:
    """Play Gold moves until the move response itself reports terminal."""
    strong = load_checkpoint(options.model)
    require(checkpoint_sha256(options.model) == options.model_sha256, "strong hash changed")
    require(strong.model_id == options.model_id, "strong model ID changed")
    config = SearchConfig(
        node_budget=options.node_budget,
        width=options.width,
        max_depth=options.max_depth,
        seed=options.seed,
    )
    document = arena_request(options.arena_client, ["transcript"], options.arena_timeout)
    require(isinstance(document.get("actions"), list), "transcript action list is malformed")
    state, resigned = replay_records(document["actions"])
    require_public_state(document, state, resigned, include_actions=True)
    require(not resigned, "oracle was invoked after resignation")
    for _ in range(10):
        if state.terminal:
            require(
                state.result == "gold_win" and state.winner == "gold",
                "strong oracle did not leave a genuine Gold victory",
            )
            print(
                f"TIDEVAULT_ORACLE_GOLD_WIN ply={state.ply} "
                f"score={state.gold_score}-{state.violet_score} "
                f"termination={state.termination}"
            )
            return
        require(state.turn == "gold", "public transaction did not return to Gold")
        result = analyze(state, strong, config)
        action = result.action
        require(action.token in document["legal_actions"], "oracle action is not public")
        print(
            f"oracle move {action.token} depth={result.completed_depth} nodes={result.nodes}",
            flush=True,
        )
        player_state = core.apply_action(state, action)
        power, slot, rotation_ring, direction = action.token.split()
        document = arena_request(
            options.arena_client,
            ["move", power, slot, rotation_ring, direction],
            options.arena_timeout,
        )
        if player_state.terminal:
            state = player_state
        else:
            latest = document.get("latest_record")
            require(isinstance(latest, Mapping), "opponent record is missing")
            opponent_action = core.parse_action(latest.get("action"))
            require(core.is_legal(player_state, opponent_action), "opponent action is illegal")
            opponent_state = core.apply_action(player_state, opponent_action)
            require_record_transition(
                latest,
                player_state,
                opponent_state,
                opponent_action,
                opponent_state.ply,
            )
            state = opponent_state
        require_public_state(document, state)
    raise OracleError("strong oracle exceeded Gold's action bound")


def parse_arguments() -> argparse.Namespace:
    """Parse the frozen strong-oracle tuple."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--arena-client", type=Path, default=Path("/app/arena"))
    parser.add_argument("--node-budget", type=int, default=12000)
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--max-depth", type=int, default=18)
    parser.add_argument("--seed", type=int, default=2026072002)
    parser.add_argument("--arena-timeout", type=int, default=30)
    options = parser.parse_args()
    require(options.model.is_file(), "strong checkpoint is missing")
    require(options.arena_client.is_file(), "public arena client is missing")
    require(HASH_RE.fullmatch(options.model_sha256) is not None, "strong hash is invalid")
    return options


def main() -> int:
    """Run the fail-closed oracle driver."""
    try:
        play(parse_arguments())
    except (OracleError, OSError, subprocess.SubprocessError, TypeError, ValueError) as error:
        print(f"tidevault oracle failed: {error}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
