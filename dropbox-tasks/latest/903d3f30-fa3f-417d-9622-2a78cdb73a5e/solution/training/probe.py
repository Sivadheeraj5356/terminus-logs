#!/usr/bin/env python3
"""Measure Tidevault balance with random and tide-aware tactical baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION))

from core import (  # noqa: E402
    DIRECTIONS,
    POWERS,
    RINGS,
    SLOTS,
    Action,
    State,
    apply_action,
    initial_state,
    legal_actions,
    state_hash,
)
from model import POLICY_FEATURE_NAMES, policy_features  # noqa: E402


def random_action(state: State, rng: random.Random) -> Action:
    """Choose uniformly from the canonical legal action set."""

    powers = [power for power in POWERS if state.inventory(state.turn)[power - 1] > 0]
    empty_slots = [slot for slot, stone in zip(SLOTS, state.board) if stone is None]
    return Action(
        rng.choice(powers),
        *rng.choice(empty_slots),
        rng.choice(RINGS),
        rng.choice(DIRECTIONS),
    )


def tactical_score(state: State, action: Action) -> int:
    """Score visible post-rotation control with extra weight at a scoring tide."""

    values = dict(
        zip(POLICY_FEATURE_NAMES, policy_features(state, action, state.turn))
    )
    return (
        1_000 * values["immediate_own_points"]
        - 1_100 * values["immediate_opp_points"]
        + 90 * values["post_own_spoke_leads"]
        - 100 * values["post_opp_spoke_leads"]
        + 20 * values["post_own_spoke_margin"]
        + 9 * values["power"]
        + 5 * values["same_ring"]
    )


def greedy_action(state: State, rng: random.Random) -> Action:
    """Choose uniformly among maximum tide-aware tactical actions."""

    actions = legal_actions(state)
    scores = [tactical_score(state, action) for action in actions]
    best = max(scores)
    choices = [action for action, score in zip(actions, scores) if score == best]
    return choices[rng.randrange(len(choices))]


def run_panel(
    games: int,
    seed: int,
    gold_policy: str,
    violet_policy: str,
) -> dict[str, object]:
    """Run one deterministic seeded baseline panel."""

    counts = {"gold_win": 0, "violet_win": 0, "draw": 0}
    total_gold = total_violet = total_abs_margin = 0
    total_gold_weight = total_violet_weight = 0
    digest = hashlib.sha256()
    policies = {"random": random_action, "greedy": greedy_action}
    for game in range(games):
        rng = random.Random(seed + game)
        state = initial_state()
        while not state.terminal:
            policy_name = gold_policy if state.turn == "gold" else violet_policy
            state = apply_action(state, policies[policy_name](state, rng))
        counts[state.result] += 1
        total_gold += state.gold_score
        total_violet += state.violet_score
        total_abs_margin += abs(state.gold_score - state.violet_score)
        total_gold_weight += sum(
            stone.power
            for stone in state.board
            if stone is not None and stone.owner == "gold"
        )
        total_violet_weight += sum(
            stone.power
            for stone in state.board
            if stone is not None and stone.owner == "violet"
        )
        digest.update(
            (
                json.dumps(
                    {
                        "game": game,
                        "gold_score": state.gold_score,
                        "result": state.result,
                        "state_hash": state_hash(state),
                        "violet_score": state.violet_score,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")
        )
    return {
        "avg_abs_margin": total_abs_margin / games,
        "avg_gold_score": total_gold / games,
        "avg_gold_weight": total_gold_weight / games,
        "avg_violet_score": total_violet / games,
        "avg_violet_weight": total_violet_weight / games,
        "draws": counts["draw"],
        "games": games,
        "gold_policy": gold_policy,
        "gold_wins": counts["gold_win"],
        "result_sha256": digest.hexdigest(),
        "seed_first": seed,
        "seed_last": seed + games - 1,
        "violet_policy": violet_policy,
        "violet_wins": counts["violet_win"],
    }


def main() -> None:
    """Run the release balance panels."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--random-games", type=int, default=50_000)
    parser.add_argument("--baseline-games", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()
    if args.random_games < 1 or args.baseline_games < 1 or args.seed < 1:
        parser.error("game counts and seed must be positive")
    panels = (
        (args.random_games, "random", "random"),
        (args.baseline_games, "greedy", "random"),
        (args.baseline_games, "random", "greedy"),
        (args.baseline_games, "greedy", "greedy"),
    )
    print("format=tidevault-baseline-probe-v1")
    print(f"command_seed={args.seed}")
    for games, gold, violet in panels:
        result = run_panel(games, args.seed, gold, violet)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
