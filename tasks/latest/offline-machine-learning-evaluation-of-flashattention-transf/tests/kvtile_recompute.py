"""Intentional import trap — real recompute lives outside candidate-readable paths."""

raise ImportError(
    "kvtile_recompute is verifier-isolated; candidate binaries must not import /tests helpers"
)
