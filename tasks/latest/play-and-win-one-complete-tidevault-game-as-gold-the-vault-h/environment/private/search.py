"""Bounded deterministic beam minimax search for Tidevault."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Optional

from core import Action, PLY_LIMIT, State, apply_action, legal_actions, state_hash
from model import LinearModel, POLICY_FEATURE_NAMES, VALUE_FEATURE_NAMES


SELECTION_PROFILE = "beam-rank-lapse-v1"


@dataclass(frozen=True)
class SearchConfig:
    """Frozen public search and weakening controls."""

    node_budget: int
    width: int
    max_depth: int
    seed: int
    selection_profile: str = SELECTION_PROFILE
    root_rank_lapse_permille: int = 0
    root_temperature_milli: int = 0

    def __post_init__(self) -> None:
        if self.node_budget < 1 or self.width < 1 or self.max_depth < 1 or self.seed < 1:
            raise ValueError("search budget, width, depth, and seed must be positive")
        if self.selection_profile != SELECTION_PROFILE:
            raise ValueError("unsupported selection profile")
        if not 0 <= self.root_rank_lapse_permille <= 1000:
            raise ValueError("rank lapse must be between 0 and 1000")
        if self.root_temperature_milli != 0:
            raise ValueError("Tidevault v1 search requires zero root temperature")


@dataclass(frozen=True)
class RankedAction:
    """One root action and its completed-search score."""

    action: Action
    score: int


@dataclass(frozen=True)
class SearchResult:
    """Deterministic search result and audit counters."""

    action: Action
    score: int
    completed_depth: int
    nodes: int
    selected_rank: int
    ranked: tuple[RankedAction, ...]


class _BudgetExhausted(Exception):
    pass


class _Context:
    def __init__(self, model: LinearModel, config: SearchConfig, root_actor: str):
        self.model = model
        self.config = config
        self.root_actor = root_actor
        self.nodes = 0

    def visit(self) -> None:
        if self.nodes >= self.config.node_budget:
            raise _BudgetExhausted
        self.nodes += 1


def _digest_tiebreak(seed: int, digest: str, purpose: str, action: Action) -> int:
    payload = f"{seed}|{digest}|{purpose}|{action.token}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _ordered_actions(
    state: State,
    model: LinearModel,
    config: SearchConfig,
    purpose: str,
) -> tuple[Action, ...]:
    digest = state_hash(state)
    actions = legal_actions(state)
    return tuple(
        sorted(
            actions,
            key=lambda action: (
                -model.policy(state, action),
                _digest_tiebreak(config.seed, digest, purpose, action),
                action.token,
            ),
        )[: config.width]
    )


def _minimax(state: State, depth: int, context: _Context) -> int:
    if state.terminal or depth == 0:
        return context.model.value(state, context.root_actor)
    actions = _ordered_actions(state, context.model, context.config, f"d{depth}")
    if not actions:
        return context.model.value(state, context.root_actor)
    maximizing = state.turn == context.root_actor
    best: Optional[int] = None
    for action in actions:
        context.visit()
        child = apply_action(state, action)
        score = _minimax(child, depth - 1, context)
        if best is None or (maximizing and score > best) or (not maximizing and score < best):
            best = score
    assert best is not None
    return best


def _root_iteration(
    state: State,
    depth: int,
    context: _Context,
) -> tuple[RankedAction, ...]:
    actions = _ordered_actions(state, context.model, context.config, "root-order")
    values: list[RankedAction] = []
    for action in actions:
        context.visit()
        child = apply_action(state, action)
        values.append(RankedAction(action, _minimax(child, depth - 1, context)))
    digest = state_hash(state)
    values.sort(
        key=lambda item: (
            -item.score,
            _digest_tiebreak(context.config.seed, digest, f"root-d{depth}", item.action),
            item.action.token,
        )
    )
    return tuple(values)


def _lapse_rank(state: State, config: SearchConfig, ranked_count: int) -> int:
    if ranked_count < 2 or config.root_rank_lapse_permille == 0:
        return 0
    payload = f"{config.seed}|{state_hash(state)}|rank-lapse".encode("ascii")
    draw = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % 1000
    return 1 if draw < config.root_rank_lapse_permille else 0


def analyze(state: State, model: LinearModel, config: SearchConfig) -> SearchResult:
    """Search one position and return the selected action plus audit evidence."""

    if state.terminal:
        raise ValueError("cannot search a terminal state")
    if not legal_actions(state):
        raise ValueError("cannot search a state without legal actions")
    context = _Context(model, config, state.turn)
    completed: tuple[RankedAction, ...] = ()
    completed_depth = 0
    depth_limit = min(config.max_depth, PLY_LIMIT - state.ply)
    for depth in range(1, depth_limit + 1):
        try:
            candidate = _root_iteration(state, depth, context)
        except _BudgetExhausted:
            break
        completed = candidate
        completed_depth = depth
    if not completed:
        action = _ordered_actions(state, model, config, "fallback")[0]
        completed = (RankedAction(action, model.policy(state, action)),)
    selected_rank = _lapse_rank(state, config, len(completed))
    selected = completed[selected_rank]
    return SearchResult(
        action=selected.action,
        score=selected.score,
        completed_depth=completed_depth,
        nodes=context.nodes,
        selected_rank=selected_rank,
        ranked=completed,
    )


def choose_action(state: State, model: LinearModel, config: SearchConfig) -> Action:
    """Return only the deterministic selected action."""

    return analyze(state, model, config).action


def _selftest() -> None:
    model = LinearModel(
        model_id="tidevault-search-selftest",
        dataset_sha256="0" * 64,
        epoch=1,
        seed=1,
        training_games=1,
        training_samples=1,
        value_weights=(0,) * len(VALUE_FEATURE_NAMES),
        policy_weights=(0,) * len(POLICY_FEATURE_NAMES),
    )
    config = SearchConfig(node_budget=32, width=8, max_depth=3, seed=1)
    first = analyze(State(), model, config)
    second = analyze(State(), model, config)
    assert first == second
    assert first.action in legal_actions(State())
    assert 0 < first.nodes <= config.node_budget


if __name__ == "__main__":
    _selftest()
