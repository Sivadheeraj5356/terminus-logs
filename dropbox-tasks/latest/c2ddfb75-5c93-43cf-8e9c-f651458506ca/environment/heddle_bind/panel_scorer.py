from __future__ import annotations

from pathlib import Path
from typing import Any

from shed_weave.phase_runner import compile_panel_row
from shed_weave.registry_slice import materialize_panel_bundle
from shed_weave.session_anchor import CompileContext, build_compile_context


def score_panel(
    panel_id: str,
    bundle: dict[str, Any],
    catalogs: dict[str, Any],
    config_dir: Path,
    ctx: CompileContext | None = None,
    dye_seed: float = 1.0,
) -> dict[str, float | str]:
    compile_ctx = ctx or build_compile_context(bundle, catalogs, config_dir)
    panel_bundle = materialize_panel_bundle(panel_id, catalogs)
    return compile_panel_row(panel_bundle, compile_ctx, catalogs["master_weavers"], dye_seed=dye_seed)
