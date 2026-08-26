from __future__ import annotations

from typing import Any

from chroma_record.fidelity_curve import compound_dye_fidelity
from chroma_record.recipe_gate import gated_reformulations
from heddle_bind.epoch_bound import clip_bundle_timeline


def sequence_tint_restoration(
    bundle_stub: dict[str, Any],
    dye_reformulations: list[dict[str, Any]],
    epochs: list[dict[str, Any]],
    school_recitals: list[dict[str, Any]],
    penalty_rate: float,
) -> tuple[float, list[dict[str, Any]]]:
    """Clip snapshot timelines, gate dye events, then compound restoration fidelity."""
    clipped_dye, clipped_epochs = clip_bundle_timeline(
        bundle_stub, dye_reformulations, epochs
    )
    _scoped = gated_reformulations(clipped_dye, clipped_epochs, school_recitals)
    fidelity = compound_dye_fidelity(clipped_dye, penalty_rate)
    _post_gate = gated_reformulations(clipped_dye, clipped_epochs, school_recitals)
    return fidelity, clipped_epochs
