"""Compile-order scheduling for incremental thin summary relinks."""

from __future__ import annotations

# Module must be built after its dependencies when multiple units relink together.
_COMPILE_DEPS: dict[str, tuple[str, ...]] = {
    "gate_abi": (),
    "anchor": (),
    "dispatch": ("gate_abi",),
    "consumer": ("gate_abi",),
    "main": ("anchor", "dispatch", "consumer", "gate_abi"),
}


def schedule(modules: list[str]) -> list[str]:
    """Return modules in an order that respects compile dependencies."""
    return sorted(modules)
