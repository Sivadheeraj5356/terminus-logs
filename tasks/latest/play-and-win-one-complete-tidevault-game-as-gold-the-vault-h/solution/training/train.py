#!/usr/bin/env python3
"""Generate deterministic Tidevault self-play and five linear checkpoints."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import sys

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION))

from core import Action, State, apply_action, initial_state, legal_actions, state_hash  # noqa: E402
from model import (  # noqa: E402
    LinearModel,
    POLICY_FEATURE_NAMES,
    VALUE_FEATURE_NAMES,
    policy_features,
    save_checkpoint,
    value_features,
)


DEFAULT_SEED = 20260719
CHECKPOINT_EPOCHS = (1, 2, 4, 8, 16)


@dataclass(frozen=True)
class PendingSample:
    """One self-play decision awaiting its terminal label."""

    state_digest: str
    actor: str
    teacher: Action
    played: Action
    value: tuple[int, ...]
    teacher_policy: tuple[int, ...]
    negatives: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class Sample:
    """One deterministically labeled training sample."""

    state_digest: str
    actor: str
    teacher: Action
    played: Action
    outcome: int
    margin: int
    value: tuple[int, ...]
    teacher_policy: tuple[int, ...]
    negatives: tuple[tuple[int, ...], ...]


def teacher_score(state: State, action: Action) -> int:
    """Score one action with the frozen tide-aware tactical teacher."""

    values = dict(
        zip(
            POLICY_FEATURE_NAMES,
            policy_features(state, action, state.turn),
        )
    )
    tide_urgency = 10 - values["plies_to_tide"]
    return (
        1_100 * values["immediate_own_points"]
        - 1_250 * values["immediate_opp_points"]
        + 105 * values["post_own_spoke_leads"]
        - 120 * values["post_opp_spoke_leads"]
        + 22 * values["post_own_spoke_margin"]
        + 5 * tide_urgency * values["post_own_spoke_margin"]
        + 13 * values["power"]
        + 7 * values["same_ring"]
        + 3 * values["same_power_left"]
    )


def _teacher_tie(seed: int, digest: str, action: Action) -> int:
    raw = f"{seed}|{digest}|teacher|{action.token}".encode("ascii")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def teacher_ranking(state: State, seed: int) -> tuple[Action, ...]:
    """Rank every legal action by the deterministic corpus teacher."""

    digest = state_hash(state)
    return tuple(
        sorted(
            legal_actions(state),
            key=lambda action: (
                -teacher_score(state, action),
                _teacher_tie(seed, digest, action),
                action.token,
            ),
        )
    )


def _negative_actions(
    ranking: tuple[Action, ...], teacher: Action
) -> tuple[Action, ...]:
    candidates = [action for action in ranking if action != teacher]
    if not candidates:
        return ()
    indexes = sorted(
        {0, len(candidates) // 3, (2 * len(candidates)) // 3, len(candidates) - 1}
    )
    return tuple(candidates[index] for index in indexes)


def generate_corpus(
    games: int, seed: int
) -> tuple[list[Sample], dict[str, int], str]:
    """Play exploratory self-play and label every decision."""

    rng = random.Random(seed)
    samples: list[Sample] = []
    counts = {"gold_win": 0, "violet_win": 0, "draw": 0, "complete": 0}
    digest = hashlib.sha256()
    for game_index in range(games):
        state = initial_state()
        pending: list[PendingSample] = []
        while not state.terminal:
            ranking = teacher_ranking(state, seed + game_index)
            teacher = ranking[0]
            draw = rng.randrange(1000)
            if draw < 260:
                played = ranking[rng.randrange(len(ranking))]
            elif draw < 540:
                played = ranking[rng.randrange(min(6, len(ranking)))]
            else:
                played = teacher
            negatives = _negative_actions(ranking, teacher)
            pending.append(
                PendingSample(
                    state_digest=state_hash(state),
                    actor=state.turn,
                    teacher=teacher,
                    played=played,
                    value=value_features(state, state.turn),
                    teacher_policy=policy_features(state, teacher, state.turn),
                    negatives=tuple(
                        policy_features(state, action, state.turn)
                        for action in negatives
                    ),
                )
            )
            state = apply_action(state, played)
        counts[state.result] += 1
        counts[state.termination] += 1
        raw_margin = state.gold_score - state.violet_score
        for pending_sample in pending:
            if state.winner is None:
                outcome = 0
            else:
                outcome = 1 if state.winner == pending_sample.actor else -1
            margin = raw_margin if pending_sample.actor == "gold" else -raw_margin
            sample = Sample(
                state_digest=pending_sample.state_digest,
                actor=pending_sample.actor,
                teacher=pending_sample.teacher,
                played=pending_sample.played,
                outcome=outcome,
                margin=margin,
                value=pending_sample.value,
                teacher_policy=pending_sample.teacher_policy,
                negatives=pending_sample.negatives,
            )
            samples.append(sample)
            line = {
                "actor": sample.actor,
                "margin": sample.margin,
                "outcome": sample.outcome,
                "played": sample.played.token,
                "state_sha256": sample.state_digest,
                "teacher": sample.teacher.token,
            }
            digest.update(
                (
                    json.dumps(line, separators=(",", ":"), sort_keys=True) + "\n"
                ).encode("ascii")
            )
    return samples, counts, digest.hexdigest()


def _dot(weights: list[int], features: tuple[int, ...]) -> int:
    return sum(weight * feature for weight, feature in zip(weights, features))


def _train_epoch(
    samples: list[Sample],
    value_weights: list[int],
    policy_weights: list[int],
    seed: int,
    epoch: int,
) -> tuple[int, int]:
    order = list(range(len(samples)))
    random.Random(seed + 100_003 * epoch).shuffle(order)
    value_updates = 0
    policy_updates = 0
    for index in order:
        sample = samples[index]
        target = sample.outcome * 24_000 + sample.margin * 700
        prediction = _dot(value_weights, sample.value)
        error = target - prediction
        denominator = max(1, sum(feature * feature for feature in sample.value))
        step = max(-8, min(8, round(error / denominator)))
        if step:
            for feature_index, feature in enumerate(sample.value):
                value_weights[feature_index] += step * feature
            value_updates += 1

        for negative in sample.negatives:
            difference = tuple(
                chosen - rejected
                for chosen, rejected in zip(sample.teacher_policy, negative)
            )
            if _dot(policy_weights, difference) <= 64:
                for feature_index, feature in enumerate(difference):
                    policy_weights[feature_index] += feature
                policy_updates += 1
    return value_updates, policy_updates


def train(output_dir: Path, games: int, seed: int) -> None:
    """Run the complete deterministic first-party training lineage."""

    output_dir.mkdir(parents=True, exist_ok=True)
    samples, counts, dataset_sha256 = generate_corpus(games, seed)
    value_weights = [0] * len(VALUE_FEATURE_NAMES)
    policy_weights = [0] * len(POLICY_FEATURE_NAMES)
    log_lines = [
        "format=tidevault-training-log-v1",
        f"seed={seed}",
        f"games={games}",
        f"samples={len(samples)}",
        f"dataset_sha256={dataset_sha256}",
        f"gold_wins={counts['gold_win']}",
        f"violet_wins={counts['violet_win']}",
        f"draws={counts['draw']}",
        f"complete={counts['complete']}",
    ]
    for epoch in range(1, max(CHECKPOINT_EPOCHS) + 1):
        value_updates, policy_updates = _train_epoch(
            samples, value_weights, policy_weights, seed, epoch
        )
        if epoch not in CHECKPOINT_EPOCHS:
            continue
        model_id = f"tidevault-linear-s{seed}-e{epoch:04d}"
        model = LinearModel(
            model_id=model_id,
            dataset_sha256=dataset_sha256,
            epoch=epoch,
            seed=seed,
            training_games=games,
            training_samples=len(samples),
            value_weights=tuple(value_weights),
            policy_weights=tuple(policy_weights),
        )
        checkpoint = output_dir / f"checkpoint-e{epoch:04d}.tvnn"
        save_checkpoint(checkpoint, model)
        checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        log_lines.append(
            f"checkpoint=e{epoch:04d} model_id={model_id} "
            f"sha256={checkpoint_sha256} value_updates={value_updates} "
            f"policy_updates={policy_updates}"
        )
    log = "\n".join(log_lines) + "\n"
    (output_dir / "training.log").write_text(log, encoding="ascii")
    print(log, end="")


def main() -> None:
    """Parse CLI arguments and train all retained checkpoints."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--games", type=int, default=1_200)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    if args.games < 1 or args.seed < 1:
        parser.error("games and seed must be positive")
    train(args.output_dir, args.games, args.seed)


if __name__ == "__main__":
    main()
