from __future__ import annotations

import os
from pathlib import Path

from shed_weave.digest_materializer import build_catalog_snapshot
from shed_weave.registry_cache import load_dye_reformulations
from shed_weave.session_anchor import CompileContext, build_compile_context
from heddle_bind.panel_scorer import score_panel
from shed_weave.loader import data_root, load_json
from shed_weave.phase_journal import resolve_replay_floor
from shed_weave.validate_bundle import bundle_is_valid


def build_pattern_genealogy(bundle_path: Path) -> dict:
    root = data_root()
    config_dir = Path("/app/config")
    bundle = load_json(bundle_path)
    snapshot = build_catalog_snapshot(root, include_overlays=False)
    catalogs = {
        **snapshot,
        "dye_reformulations": load_dye_reformulations(root),
    }
    if not bundle_is_valid(bundle, catalogs):
        raise ValueError("bundle failed structural validation")

    replay_floor = 0
    if os.environ.get("TRACE_INCREMENTAL") == "1":
        replay_floor = resolve_replay_floor(root, str(bundle["bundle_id"]))

    ctx = build_compile_context(bundle, catalogs, config_dir)
    ctx = CompileContext(
        bundle_id=ctx.bundle_id,
        policy_family=ctx.policy_family,
        snapshot_as_of=ctx.snapshot_as_of,
        blend=ctx.blend,
        network_seal=ctx.network_seal,
        replay_floor=replay_floor,
    )
    sequential = bundle.get("panel_coupling") == "sequential_drift"
    dye_seed = 1.0
    panels_out = []
    for entry in bundle["panels"]:
        row = score_panel(
            entry["panel_id"],
            bundle,
            catalogs,
            config_dir,
            ctx=ctx,
            dye_seed=dye_seed,
        )
        panels_out.append(row)
        if sequential:
            dye_seed = float(row["dye_fidelity"])
    indices = [row["influence_index"] for row in panels_out]
    weakest = min(panels_out, key=lambda row: row["influence_index"])

    return {
        "bundle_id": bundle["bundle_id"],
        "network_seal": ctx.network_seal,
        "panels": panels_out,
        "summary": {
            "mean_influence": round(sum(indices) / len(indices), 2),
            "weakest_panel": weakest["panel_id"],
        },
    }
