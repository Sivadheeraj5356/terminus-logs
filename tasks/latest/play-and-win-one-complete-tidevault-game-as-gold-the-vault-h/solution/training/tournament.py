#!/usr/bin/env python3
"""Run deterministic color-swapped Tidevault checkpoint tournaments."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import time

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION))

from core import State, apply_action, initial_state, state_hash  # noqa: E402
from model import LinearModel, load_checkpoint  # noqa: E402
from search import SearchConfig, analyze  # noqa: E402


def play_game(
    gold: LinearModel,
    violet: LinearModel,
    gold_config: SearchConfig,
    violet_config: SearchConfig,
) -> tuple[State, int, float]:
    """Play one game and return state, total nodes, and slowest move."""

    state = initial_state()
    nodes = 0
    max_seconds = 0.0
    while not state.terminal:
        model = gold if state.turn == "gold" else violet
        config = gold_config if state.turn == "gold" else violet_config
        started = time.monotonic()
        result = analyze(state, model, config)
        max_seconds = max(max_seconds, time.monotonic() - started)
        nodes += result.nodes
        state = apply_action(state, result.action)
    return state, nodes, max_seconds


def config(
    budget: int,
    width: int,
    depth: int,
    seed: int,
    lapse: int,
) -> SearchConfig:
    """Construct one exact tournament configuration."""

    return SearchConfig(
        node_budget=budget,
        width=width,
        max_depth=depth,
        seed=seed,
        root_rank_lapse_permille=lapse,
    )


def main() -> None:
    """Run the requested exact model and search matchup."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--a", type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    parser.add_argument("--games-per-color", type=int, default=3)
    parser.add_argument("--a-budget", type=int, default=2_048)
    parser.add_argument("--a-width", type=int, default=24)
    parser.add_argument("--a-depth", type=int, default=18)
    parser.add_argument("--a-lapse", type=int, default=0)
    parser.add_argument("--b-budget", type=int, default=2_048)
    parser.add_argument("--b-width", type=int, default=24)
    parser.add_argument("--b-depth", type=int, default=18)
    parser.add_argument("--b-lapse", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()
    if min(
        args.games_per_color,
        args.a_budget,
        args.a_width,
        args.a_depth,
        args.b_budget,
        args.b_width,
        args.b_depth,
        args.seed,
    ) < 1:
        parser.error("game count, search values, and seed must be positive")
    if not 0 <= args.a_lapse <= 1000 or not 0 <= args.b_lapse <= 1000:
        parser.error("lapse values must be between 0 and 1000")

    model_a = load_checkpoint(args.a)
    model_b = load_checkpoint(args.b)
    a_wins = b_wins = draws = 0
    lines: list[str] = []
    for seating in range(2):
        for game in range(args.games_per_color):
            game_seed = args.seed + seating * 10_000 + game
            a_config = config(
                args.a_budget,
                args.a_width,
                args.a_depth,
                game_seed * 2 + 1,
                args.a_lapse,
            )
            b_config = config(
                args.b_budget,
                args.b_width,
                args.b_depth,
                game_seed * 2 + 2,
                args.b_lapse,
            )
            if seating == 0:
                gold, violet = model_a, model_b
                gold_config, violet_config = a_config, b_config
            else:
                gold, violet = model_b, model_a
                gold_config, violet_config = b_config, a_config
            final, nodes, max_seconds = play_game(
                gold, violet, gold_config, violet_config
            )
            if final.winner is None:
                draws += 1
                model_winner = "draw"
            elif (seating == 0 and final.winner == "gold") or (
                seating == 1 and final.winner == "violet"
            ):
                a_wins += 1
                model_winner = "a"
            else:
                b_wins += 1
                model_winner = "b"
            lines.append(
                f"seating={seating} game={game} seed={game_seed} "
                f"winner={model_winner} result={final.result} "
                f"score={final.gold_score}-{final.violet_score} ply={final.ply} "
                f"nodes={nodes} max_move_ms={max_seconds * 1000:.3f} "
                f"state_sha256={state_hash(final)}"
            )
    header = [
        "format=tidevault-tournament-v1",
        f"a={model_a.model_id}",
        f"b={model_b.model_id}",
        f"a_tuple={args.a_budget}/{args.a_width}/{args.a_depth}/{args.a_lapse}",
        f"b_tuple={args.b_budget}/{args.b_width}/{args.b_depth}/{args.b_lapse}",
        f"a_wins={a_wins}",
        f"b_wins={b_wins}",
        f"draws={draws}",
    ]
    output = "\n".join(header + lines) + "\n"
    print(output, end="")
    print(f"output_sha256={hashlib.sha256(output.encode('ascii')).hexdigest()}")


if __name__ == "__main__":
    main()
