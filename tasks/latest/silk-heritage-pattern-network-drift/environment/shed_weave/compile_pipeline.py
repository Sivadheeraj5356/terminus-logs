from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chroma_record.recipe_gate import gated_reformulations
from relay_cordage.transfer_gate import merchant_permits_relay
from relay_cordage.route_span import school_continuity_span
from atelier_chain.lineage_map import compile_lineage_map
from atelier_chain.weaver_trust import walk_weaver_trust
from heddle_bind.catalog_resolver import PanelEntry
from heddle_bind.coeff_loader import letter_weight
from shed_weave.tint_sequencer import sequence_tint_restoration
from shed_weave.registry_slice import PanelBundle
from shed_weave.session_anchor import CompileContext


@dataclass
class _SessionPhaseState:
    replay_floor: int = 0
    policy_family: str = "standard"


_SESSION = _SessionPhaseState()


def _ledger_stub(ctx: CompileContext) -> dict[str, Any]:
    payload: dict[str, Any] = {"bundle_id": ctx.bundle_id}
    if ctx.snapshot_as_of is not None:
        payload["genealogy_snapshot"] = {"as_of_year": ctx.snapshot_as_of}
    return payload


def _effective_replay_floor(ctx: CompileContext) -> int:
    if ctx.replay_floor > 0:
        _SESSION.replay_floor = ctx.replay_floor
        return ctx.replay_floor
    if ctx.policy_family != _SESSION.policy_family:
        _SESSION.policy_family = ctx.policy_family
        return 0
    return _SESSION.replay_floor


def run_panel_phases(
    bundle: PanelBundle,
    ctx: CompileContext,
    master_weavers: dict[str, Any],
) -> dict[str, float | str]:
    entry: PanelEntry = bundle.entry
    ledger_stub = _ledger_stub(ctx)

    lineage_map = compile_lineage_map(
        master_weavers["mentor_of"],
        master_weavers.get("lineage_epochs", {}),
        entry.completion_year,
    )
    lineage = walk_weaver_trust(entry.weaver_id, lineage_map, master_weavers)

    dye_fidelity, _clipped_epochs = sequence_tint_restoration(
        ledger_stub,
        list(bundle.dye_reformulations),
        list(bundle.epochs),
        bundle.school_recitals,
        ctx.blend["dye_penalty_rate"],
    )
    _scoped = gated_reformulations(
        bundle.dye_reformulations,
        bundle.epochs,
        bundle.school_recitals,
    )

    replay_floor = _effective_replay_floor(ctx)
    coverage = school_continuity_span(
        bundle.epochs,
        bundle.loom_letters,
        bundle.sales,
        merchant_permits_relay,
        replay_floor,
    )

    cert_term = letter_weight(coverage, ctx.blend)
    fair = round(bundle.base_appraisal * lineage * dye_fidelity * cert_term, 2)
    base = bundle.base_appraisal
    index = round((fair / base) * 100, 2) if base > 0 else 0.0

    return {
        "panel_id": entry.panel_id,
        "weaver_lineage": round(lineage, 6),
        "dye_fidelity": round(dye_fidelity, 6),
        "school_continuity": round(coverage, 4),
        "heritage_score": fair,
        "influence_index": index,
    }
