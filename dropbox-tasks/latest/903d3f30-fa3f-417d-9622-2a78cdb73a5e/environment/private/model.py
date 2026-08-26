"""Deterministic quantized linear policy/value model for Tidevault."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Optional

from core import (
    Action,
    RINGS,
    SECTORS,
    TIDE_PLIES,
    State,
    Stone,
    legal_actions,
    score_spokes,
    settled_slot_for_action,
    slot_index,
)


FORMAT = "tidevault-linear-v1"
WEIGHT_SCALE = 100_000

VALUE_FEATURE_NAMES = (
    "bias",
    "score_diff",
    "ply",
    "tides_completed",
    "plies_to_tide",
    "own_p1_left",
    "own_p2_left",
    "own_p3_left",
    "opp_p1_left",
    "opp_p2_left",
    "opp_p3_left",
    "empty_slots",
    "own_board_weight",
    "opp_board_weight",
    "own_spoke_leads",
    "opp_spoke_leads",
    "tied_spokes",
    "own_spoke_margin",
    "own_max_spoke",
    "opp_max_spoke",
    "own_ring_i_weight",
    "opp_ring_i_weight",
    "own_ring_m_weight",
    "opp_ring_m_weight",
    "own_ring_o_weight",
    "opp_ring_o_weight",
)

POLICY_FEATURE_NAMES = (
    "bias",
    "power_1",
    "power_2",
    "power_3",
    "power",
    "placement_ring_i",
    "placement_ring_m",
    "placement_ring_o",
    "rotation_ring_i",
    "rotation_ring_m",
    "rotation_ring_o",
    "same_ring",
    "direction_cw",
    "direction_ccw",
    "settled_sector",
    "ply",
    "plies_to_tide",
    "score_diff",
    "same_power_left",
    "post_own_spoke_leads",
    "post_opp_spoke_leads",
    "post_tied_spokes",
    "post_own_spoke_margin",
    "immediate_own_points",
    "immediate_opp_points",
)


def _perspective(actor: str) -> tuple[str, str, int]:
    if actor == "gold":
        return "gold", "violet", 1
    if actor == "violet":
        return "violet", "gold", -1
    raise ValueError("actor must be gold or violet")


def _plies_to_next_tide(ply: int) -> int:
    for tide_ply in TIDE_PLIES:
        if tide_ply > ply:
            return tide_ply - ply
    return 0


def _spoke_summary(
    board: tuple[Optional[Stone], ...],
    actor: str,
) -> tuple[int, int, int, int, int, tuple[int, ...]]:
    _, _, sign = _perspective(actor)
    margins = tuple(
        sign * (spoke.gold_weight - spoke.violet_weight)
        for spoke in score_spokes(board)
    )
    return (
        sum(margin > 0 for margin in margins),
        sum(margin < 0 for margin in margins),
        sum(margin == 0 for margin in margins),
        sum(max(0, margin) for margin in margins),
        sum(max(0, -margin) for margin in margins),
        margins,
    )


def value_features(state: State, actor: str) -> tuple[int, ...]:
    """Extract integer value features from actor's perspective."""

    own, opponent, sign = _perspective(actor)
    own_inventory = state.inventory(own)
    opponent_inventory = state.inventory(opponent)
    own_stones = [
        stone for stone in state.board if stone is not None and stone.owner == own
    ]
    opponent_stones = [
        stone for stone in state.board if stone is not None and stone.owner == opponent
    ]
    own_leads, opponent_leads, ties, _positive, _negative, margins = _spoke_summary(
        state.board, actor
    )
    ring_weights: list[int] = []
    for ring in RINGS:
        ring_stones = (
            state.board[slot_index(ring, sector)] for sector in SECTORS
        )
        ring_values = tuple(ring_stones)
        ring_weights.append(
            sum(stone.power for stone in ring_values if stone is not None and stone.owner == own)
        )
        ring_weights.append(
            sum(
                stone.power
                for stone in ring_values
                if stone is not None and stone.owner == opponent
            )
        )
    values = (
        1,
        sign * (state.gold_score - state.violet_score),
        state.ply,
        len(state.tides),
        _plies_to_next_tide(state.ply),
        *own_inventory,
        *opponent_inventory,
        sum(stone is None for stone in state.board),
        sum(stone.power for stone in own_stones),
        sum(stone.power for stone in opponent_stones),
        own_leads,
        opponent_leads,
        ties,
        sum(margins),
        max((0, *margins)),
        max((0, *(-margin for margin in margins))),
        *ring_weights,
    )
    assert len(values) == len(VALUE_FEATURE_NAMES)
    return values


def _project_board(state: State, action: Action, actor: str) -> tuple[Optional[Stone], ...]:
    board = list(state.board)
    board[slot_index(action.placement_ring, action.placement_sector)] = Stone(
        f"S{state.ply + 1:02d}", actor, action.power
    )
    base = slot_index(action.rotation_ring, "A")
    old = board[base : base + len(SECTORS)]
    delta = 1 if action.direction == "CW" else -1
    for old_sector, stone in enumerate(old):
        board[base + (old_sector + delta) % len(SECTORS)] = stone
    return tuple(board)


def policy_features(state: State, action: Action, actor: str) -> tuple[int, ...]:
    """Extract integer action-ordering features from actor's perspective."""

    _, _, sign = _perspective(actor)
    if not isinstance(action, Action):
        raise ValueError("action has the wrong type")
    post_board = _project_board(state, action, actor)
    post = _spoke_summary(post_board, actor)
    next_ply = state.ply + 1
    immediate_own = post[0] if next_ply in TIDE_PLIES else 0
    immediate_opp = post[1] if next_ply in TIDE_PLIES else 0
    settled = settled_slot_for_action(action)
    values = (
        1,
        int(action.power == 1),
        int(action.power == 2),
        int(action.power == 3),
        action.power,
        int(action.placement_ring == "I"),
        int(action.placement_ring == "M"),
        int(action.placement_ring == "O"),
        int(action.rotation_ring == "I"),
        int(action.rotation_ring == "M"),
        int(action.rotation_ring == "O"),
        int(action.placement_ring == action.rotation_ring),
        int(action.direction == "CW"),
        int(action.direction == "CCW"),
        SECTORS.index(settled[1]),
        state.ply,
        _plies_to_next_tide(state.ply),
        sign * (state.gold_score - state.violet_score),
        state.inventory(actor)[action.power - 1],
        post[0],
        post[1],
        post[2],
        sum(post[5]),
        immediate_own,
        immediate_opp,
    )
    assert len(values) == len(POLICY_FEATURE_NAMES)
    return values


@dataclass(frozen=True)
class LinearModel:
    """One frozen quantized linear policy/value checkpoint."""

    model_id: str
    dataset_sha256: str
    epoch: int
    seed: int
    training_games: int
    training_samples: int
    value_weights: tuple[int, ...]
    policy_weights: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.model_id or not self.dataset_sha256:
            raise ValueError("model identity and dataset digest are required")
        if len(self.dataset_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.dataset_sha256
        ):
            raise ValueError("dataset digest must be lowercase SHA-256")
        if self.epoch < 1 or self.seed < 1:
            raise ValueError("epoch and seed must be positive")
        if self.training_games < 1 or self.training_samples < 1:
            raise ValueError("training counts must be positive")
        if len(self.value_weights) != len(VALUE_FEATURE_NAMES):
            raise ValueError("wrong value weight count")
        if len(self.policy_weights) != len(POLICY_FEATURE_NAMES):
            raise ValueError("wrong policy weight count")
        if any(type(weight) is not int for weight in self.value_weights + self.policy_weights):
            raise ValueError("checkpoint weights must be integers")

    def value(self, state: State, actor: str) -> int:
        """Return the quantized position value from actor's perspective."""

        if state.terminal:
            opponent = "violet" if actor == "gold" else "gold"
            margin = state.score(actor) - state.score(opponent)
            if state.winner == actor:
                return 1_000_000_000 + 1_000_000 * margin
            if state.winner is None:
                return 0
            return -1_000_000_000 + 1_000_000 * margin
        return sum(
            weight * feature
            for weight, feature in zip(self.value_weights, value_features(state, actor))
        )

    def policy(self, state: State, action: Action, actor: Optional[str] = None) -> int:
        """Return the quantized action-ordering score."""

        color = state.turn if actor is None else actor
        return sum(
            weight * feature
            for weight, feature in zip(
                self.policy_weights, policy_features(state, action, color)
            )
        )

    def to_object(self) -> dict[str, object]:
        """Return the exact checkpoint object."""

        return {
            "dataset_sha256": self.dataset_sha256,
            "epoch": self.epoch,
            "format": FORMAT,
            "model_id": self.model_id,
            "policy_feature_names": list(POLICY_FEATURE_NAMES),
            "policy_weights": list(self.policy_weights),
            "seed": self.seed,
            "training_games": self.training_games,
            "training_samples": self.training_samples,
            "value_feature_names": list(VALUE_FEATURE_NAMES),
            "value_weights": list(self.value_weights),
            "weight_scale": WEIGHT_SCALE,
        }


def canonical_checkpoint_bytes(model: LinearModel) -> bytes:
    """Serialize one checkpoint byte-for-byte."""

    return (
        json.dumps(
            model.to_object(), ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    ).encode("ascii")


def save_checkpoint(path: str | Path, model: LinearModel) -> None:
    """Write one canonical `.tvnn` checkpoint."""

    target = Path(path)
    if target.suffix != ".tvnn":
        raise ValueError("Tidevault checkpoint path must end in .tvnn")
    target.write_bytes(canonical_checkpoint_bytes(model))


def load_checkpoint(path: str | Path) -> LinearModel:
    """Load and strictly validate one canonical checkpoint."""

    target = Path(path)
    if target.suffix != ".tvnn":
        raise ValueError("Tidevault checkpoint path must end in .tvnn")
    raw = target.read_bytes()
    try:
        value = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("checkpoint is not canonical ASCII JSON") from error
    expected_keys = {
        "dataset_sha256",
        "epoch",
        "format",
        "model_id",
        "policy_feature_names",
        "policy_weights",
        "seed",
        "training_games",
        "training_samples",
        "value_feature_names",
        "value_weights",
        "weight_scale",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError("checkpoint has wrong keys")
    if (
        value["format"] != FORMAT
        or value["weight_scale"] != WEIGHT_SCALE
        or value["value_feature_names"] != list(VALUE_FEATURE_NAMES)
        or value["policy_feature_names"] != list(POLICY_FEATURE_NAMES)
    ):
        raise ValueError("checkpoint architecture differs from Tidevault linear v1")
    model = LinearModel(
        model_id=value["model_id"],
        dataset_sha256=value["dataset_sha256"],
        epoch=value["epoch"],
        seed=value["seed"],
        training_games=value["training_games"],
        training_samples=value["training_samples"],
        value_weights=tuple(value["value_weights"]),
        policy_weights=tuple(value["policy_weights"]),
    )
    if raw != canonical_checkpoint_bytes(model):
        raise ValueError("checkpoint bytes are not canonical")
    return model


def checkpoint_sha256(path: str | Path) -> str:
    """Hash one checkpoint file."""

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ranked_actions(model: LinearModel, state: State) -> tuple[Action, ...]:
    """Order all legal moves by model score, then canonical token."""

    return tuple(
        sorted(
            legal_actions(state),
            key=lambda action: (-model.policy(state, action), action.token),
        )
    )


def _selftest() -> None:
    state = State()
    action = Action(2, "I", "A", "M", "CW")
    assert len(value_features(state, "gold")) == len(VALUE_FEATURE_NAMES)
    assert len(policy_features(state, action, "gold")) == len(POLICY_FEATURE_NAMES)
    model = LinearModel(
        model_id="tidevault-selftest",
        dataset_sha256="0" * 64,
        epoch=1,
        seed=1,
        training_games=1,
        training_samples=1,
        value_weights=(0,) * len(VALUE_FEATURE_NAMES),
        policy_weights=(0,) * len(POLICY_FEATURE_NAMES),
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "model.tvnn"
        save_checkpoint(path, model)
        assert load_checkpoint(path) == model
        assert len(checkpoint_sha256(path)) == 64


if __name__ == "__main__":
    _selftest()
