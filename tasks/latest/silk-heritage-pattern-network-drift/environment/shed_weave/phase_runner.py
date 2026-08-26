from __future__ import annotations

from typing import Any

from shed_weave.compile_pipeline import run_panel_phases
from shed_weave.registry_slice import PanelBundle
from shed_weave.session_anchor import CompileContext


def compile_panel_row(
    bundle: PanelBundle,
    ctx: CompileContext,
    master_weavers: dict[str, Any],
    dye_seed: float = 1.0,
) -> dict[str, float | str]:
    return run_panel_phases(bundle, ctx, master_weavers)
