#!/usr/bin/env python3
"""Run a deterministic equal-budget Tidevault checkpoint screen."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from itertools import combinations
from pathlib import Path
import sys

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION))

from core import State, apply_action, initial_state, state_hash  # noqa: E402
from model import LinearModel, load_checkpoint  # noqa: E402
from search import SearchConfig, analyze  # noqa: E402


DEFAULT_CHECKPOINT_DIR = SOLUTION / "training-output" / "tidevault-linear-v1"


def parse_epochs(value: str) -> tuple[int, ...]:
    """Parse a strictly increasing comma-separated epoch list."""

    try:
        epochs = tuple(int(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("epochs must be comma-separated integers") from error
    if len(epochs) < 2 or any(epoch < 1 for epoch in epochs):
        raise argparse.ArgumentTypeError("at least two positive epochs are required")
    if tuple(sorted(set(epochs))) != epochs:
        raise argparse.ArgumentTypeError("epochs must be unique and increasing")
    return epochs


def checkpoint(directory: Path, epoch: int) -> Path:
    """Return one retained checkpoint path."""

    return directory / f"checkpoint-e{epoch:04d}.tvnn"


def play(
    gold: LinearModel,
    violet: LinearModel,
    gold_config: SearchConfig,
    violet_config: SearchConfig,
) -> tuple[State, int]:
    """Play one deterministic screen game."""

    state = initial_state()
    total_nodes = 0
    while not state.terminal:
        model = gold if state.turn == "gold" else violet
        config = gold_config if state.turn == "gold" else violet_config
        result = analyze(state, model, config)
        total_nodes += result.nodes
        state = apply_action(state, result.action)
    return state, total_nodes


def main() -> None:
    """Screen every checkpoint pair in both colors."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--epochs", type=parse_epochs, default=parse_epochs("1,2,4,8,16"))
    parser.add_argument("--node-budget", type=int, default=512)
    parser.add_argument("--width", type=int, default=24)
    parser.add_argument("--max-depth", type=int, default=18)
    parser.add_argument("--games-per-color", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()
    if min(
        args.node_budget,
        args.width,
        args.max_depth,
        args.games_per_color,
        args.seed,
    ) < 1:
        parser.error("search values, games, and seed must be positive")

    models = {
        epoch: load_checkpoint(checkpoint(args.checkpoint_dir, epoch))
        for epoch in args.epochs
    }
    totals = {epoch: defaultdict(int) for epoch in args.epochs}
    lines = [
        "format=tidevault-checkpoint-screen-v1",
        f"epochs={','.join(str(epoch) for epoch in args.epochs)}",
        f"tuple={args.node_budget}/{args.width}/{args.max_depth}/0",
        f"base_seed={args.seed}",
        f"games_per_color={args.games_per_color}",
    ]
    for pair_index, (left, right) in enumerate(combinations(args.epochs, 2)):
        pair_counts = {"left": 0, "right": 0, "draw": 0}
        for seating in range(2):
            for game in range(args.games_per_color):
                seed = args.seed + pair_index * 100 + seating * 10 + game
                left_config = SearchConfig(
                    args.node_budget, args.width, args.max_depth, seed * 2 + 1
                )
                right_config = SearchConfig(
                    args.node_budget, args.width, args.max_depth, seed * 2 + 2
                )
                if seating == 0:
                    gold, violet = models[left], models[right]
                    gold_config, violet_config = left_config, right_config
                else:
                    gold, violet = models[right], models[left]
                    gold_config, violet_config = right_config, left_config
                final, nodes = play(gold, violet, gold_config, violet_config)
                if final.winner is None:
                    pair_counts["draw"] += 1
                    totals[left]["draw"] += 1
                    totals[right]["draw"] += 1
                    winner = "draw"
                else:
                    left_won = (seating == 0 and final.winner == "gold") or (
                        seating == 1 and final.winner == "violet"
                    )
                    winner_epoch = left if left_won else right
                    loser_epoch = right if left_won else left
                    pair_counts["left" if left_won else "right"] += 1
                    totals[winner_epoch]["win"] += 1
                    totals[loser_epoch]["loss"] += 1
                    winner = f"e{winner_epoch}"
                lines.append(
                    f"game pair={pair_index} left=e{left} right=e{right} "
                    f"seating={seating} index={game} seed={seed} winner={winner} "
                    f"result={final.result} score={final.gold_score}-{final.violet_score} "
                    f"ply={final.ply} nodes={nodes} state_sha256={state_hash(final)}"
                )
        lines.append(
            f"pair left=e{left} right=e{right} left_wins={pair_counts['left']} "
            f"draws={pair_counts['draw']} right_wins={pair_counts['right']}"
        )
    for epoch in args.epochs:
        lines.append(
            f"total epoch=e{epoch} wins={totals[epoch]['win']} "
            f"draws={totals[epoch]['draw']} losses={totals[epoch]['loss']}"
        )
    payload = "\n".join(lines) + "\n"
    print(payload, end="")
    print(f"payload_sha256={hashlib.sha256(payload.encode('ascii')).hexdigest()}")


if __name__ == "__main__":
    main()
