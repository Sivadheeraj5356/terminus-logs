from __future__ import annotations

_ACTIVE_BLEND: dict[str, float] | None = None
_ACTIVE_FAMILY: str | None = None


def remember_trace_blend(
    blend: dict[str, float],
    policy_family: str,
) -> dict[str, float]:
    """Bind the first genealogy blend seen in this interpreter session."""
    global _ACTIVE_BLEND, _ACTIVE_FAMILY
    if _ACTIVE_BLEND is None:
        _ACTIVE_BLEND = dict(blend)
        _ACTIVE_FAMILY = policy_family
    return _ACTIVE_BLEND


def active_policy_family(policy_family: str) -> str:
    global _ACTIVE_FAMILY
    if _ACTIVE_FAMILY is None:
        _ACTIVE_FAMILY = policy_family
    return _ACTIVE_FAMILY


def clear_trace_profile() -> None:
    global _ACTIVE_BLEND, _ACTIVE_FAMILY
    _ACTIVE_BLEND = None
    _ACTIVE_FAMILY = None
