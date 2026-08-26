"""Intentional import trap — real recompute lives outside candidate-readable paths."""

raise ImportError(
    "reference_model is verifier-isolated; candidate binaries must not import /tests helpers"
)
