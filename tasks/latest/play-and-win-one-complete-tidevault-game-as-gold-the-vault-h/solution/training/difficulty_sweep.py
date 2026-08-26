#!/usr/bin/env python3
"""Sweep runtime strength against a human-like tide-aware Gold proxy."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import random
import sys

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION))

from core import Action, State, apply_action, initial_state, legal_actions, state_hash  # noqa: E402
from model import POLICY_FEATURE_NAMES, load_checkpoint, policy_features  # noqa: E402
from search import SearchConfig, analyze  # noqa: E402


DEFAULT_MODEL = (
    SOLUTION
    / "training-output"
    / "tidevault-linear-v1"
    / "checkpoint-e0016.tvnn"
)


def parse_budgets(value: str) -> tuple[tuple[int, int], ...]:
    """Parse `budget:games` pairs from one comma-separated value."""

    pairs: list[tuple[int, int]] = []
    try:
        for item in value.split(","):
            budget, games = (int(part) for part in item.split(":"))
            if budget < 1 or games < 1:
                raise ValueError
            pairs.append((budget, games))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "budgets must look like 256:8,512:8 with positive integers"
        ) from error
    if not pairs:
        raise argparse.ArgumentTypeError("at least one budget is required")
    return tuple(pairs)


def proxy_score(state: State, action: Action) -> int:
    """Score a move using visible tide timing and post-rotation spoke control."""

    values = dict(
        zip(POLICY_FEATURE_NAMES, policy_features(state, action, state.turn))
    )
    urgency = 10 - values["plies_to_tide"]
    settled_center = 3 - abs(3 - values["settled_sector"])
    return (
        1_300 * values["immediate_own_points"]
        - 1_450 * values["immediate_opp_points"]
        + (80 + 8 * urgency) * values["post_own_spoke_leads"]
        - (90 + 9 * urgency) * values["post_opp_spoke_leads"]
        + (14 + 2 * urgency) * values["post_own_spoke_margin"]
        + 11 * values["power"]
        + 5 * values["same_ring"]
        + settled_center
    )


def proxy_action(state: State, rng: random.Random) -> Action:
    """Choose uniformly among maximum-scoring human-like moves."""

    actions = legal_actions(state)
    values = [proxy_score(state, action) for action in actions]
    best = max(values)
    candidates = [action for action, value in zip(actions, values) if value == best]
    return candidates[rng.randrange(len(candidates))]


def main() -> None:
    """Run the exact runtime-budget difficulty panel."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--budgets",
        type=parse_budgets,
        default=parse_budgets("4096:4,2048:8,1024:8,512:8,256:8"),
    )
    parser.add_argument("--width", type=int, default=24)
    parser.add_argument("--max-depth", type=int, default=18)
    parser.add_argument("--runtime-seed", type=int, default=20260719)
    parser.add_argument("--gold-seed", type=int, default=20260719)
    args = parser.parse_args()
    if min(args.width, args.max_depth, args.runtime_seed, args.gold_seed) < 1:
        parser.error("width, depth, and seeds must be positive")

    runtime = load_checkpoint(args.runtime_model)
    lines = [
        "format=tidevault-difficulty-sweep-v1",
        f"runtime_model_id={runtime.model_id}",
        f"runtime_dataset_sha256={runtime.dataset_sha256}",
        f"runtime_seed={args.runtime_seed}",
        f"width={args.width}",
        f"max_depth={args.max_depth}",
        f"gold_seed_first={args.gold_seed}",
        "gold_policy=uniform-among-max-tide-aware-visible-score",
    ]
    for budget, games in args.budgets:
        gold_wins = draws = violet_wins = 0
        config = SearchConfig(
            budget,
            args.width,
            args.max_depth,
            args.runtime_seed,
        )
        for game in range(games):
            seed = args.gold_seed + game
            rng = random.Random(seed)
            state = initial_state()
            while not state.terminal:
                if state.turn == "gold":
                    action = proxy_action(state, rng)
                else:
                    action = analyze(state, runtime, config).action
                state = apply_action(state, action)
            if state.result == "gold_win":
                gold_wins += 1
            elif state.result == "violet_win":
                violet_wins += 1
            else:
                draws += 1
            lines.append(
                f"game budget={budget} index={game} seed={seed} "
                f"result={state.result} score={state.gold_score}-{state.violet_score} "
                f"ply={state.ply} state_sha256={state_hash(state)}"
            )
        lines.append(
            f"total budget={budget} gold_wins={gold_wins} draws={draws} "
            f"violet_wins={violet_wins} games={games}"
        )
    payload = "\n".join(lines) + "\n"
    print(payload, end="")
    print(f"payload_sha256={hashlib.sha256(payload.encode('ascii')).hexdigest()}")


if __name__ == "__main__":
    main()
