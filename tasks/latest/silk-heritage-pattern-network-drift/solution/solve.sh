#!/usr/bin/env bash
set -euo pipefail

cd /app

python3 << 'PY'
from pathlib import Path

Path("/app/shed_weave/loader.py").write_text('''from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_registry(directory: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in sorted(directory.glob("*.json")):
        payload = load_json(path)
        merged.update(payload)
    return merged


def data_root() -> Path:
    override = os.environ.get("TRACE_DATA_ROOT")
    if override:
        return Path(override)
    return Path("/app/data")
''')

Path("/app/shed_weave/trace_profile.py").write_text('''from __future__ import annotations


def remember_trace_blend(
    blend: dict[str, float],
    policy_family: str,
) -> dict[str, float]:
    _ = policy_family
    return dict(blend)


def active_policy_family(policy_family: str) -> str:
    return policy_family


def clear_trace_profile() -> None:
    return None
''')

Path("/app/shed_weave/tint_sequencer.py").write_text('''from __future__ import annotations

from typing import Any

from chroma_record.recipe_gate import gated_reformulations
from chroma_record.fidelity_curve import compound_dye_fidelity
from heddle_bind.epoch_bound import clip_bundle_timeline


def sequence_tint_restoration(
    bundle_stub: dict[str, Any],
    dye_reformulations: list[dict[str, Any]],
    epochs: list[dict[str, Any]],
    school_recitals: list[dict[str, Any]],
    penalty_rate: float,
    dye_seed: float = 1.0,
) -> tuple[float, list[dict[str, Any]]]:
    clipped_dye, clipped_epochs = clip_bundle_timeline(
        bundle_stub, dye_reformulations, epochs
    )
    scoped = gated_reformulations(clipped_dye, clipped_epochs, school_recitals)
    fidelity = compound_dye_fidelity(scoped, penalty_rate, dye_seed)
    return fidelity, clipped_epochs
''')

Path("/app/shed_weave/compile_window.py").write_text(
    Path("/app/shed_weave/compile_window.py").read_text().replace(
        """def classify_segment(window: ReplayWindow, seg: SegmentRef) -> WindowVerdict:
    incremental = os.environ.get("TRACE_INCREMENTAL") == "1"
    if not incremental and seg.rotation_id % 2 != 0:
        return WindowVerdict.SKIP
    if seg.rotation_id > 0 and seg.rotation_id < window.rotation_floor:
        return WindowVerdict.SKIP
    if seg.generation <= window.cutoff:
        return WindowVerdict.INCLUDE
    return WindowVerdict.SKIP""",
        """def classify_segment(window: ReplayWindow, seg: SegmentRef) -> WindowVerdict:
    if seg.rotation_id > 0 and seg.rotation_id < window.rotation_floor:
        return WindowVerdict.SKIP
    if seg.generation <= window.cutoff:
        return WindowVerdict.INCLUDE
    return WindowVerdict.SKIP""",
    )
)

Path("/app/shed_weave/digest_materializer.py").write_text(
    Path("/app/shed_weave/digest_materializer.py").read_text().replace(
        "        separators=(\",\", \":\"),\n",
        "",
    )
)

Path("/app/shed_weave/compile_pipeline.py").write_text('''from __future__ import annotations

from typing import Any

from relay_cordage.transfer_gate import merchant_permits_relay
from relay_cordage.route_span import school_continuity_span
from atelier_chain.weaver_trust import walk_weaver_trust
from heddle_bind.catalog_resolver import PanelEntry
from heddle_bind.coeff_loader import letter_weight
from shed_weave.tint_sequencer import sequence_tint_restoration
from shed_weave.registry_slice import PanelBundle
from shed_weave.session_anchor import CompileContext


def _ledger_stub(ctx: CompileContext) -> dict[str, Any]:
    payload: dict[str, Any] = {"bundle_id": ctx.bundle_id}
    if ctx.snapshot_as_of is not None:
        payload["genealogy_snapshot"] = {"as_of_year": ctx.snapshot_as_of}
    return payload


def run_panel_phases(
    bundle: PanelBundle,
    ctx: CompileContext,
    master_weavers: dict[str, Any],
    dye_seed: float = 1.0,
) -> dict[str, float | str]:
    entry: PanelEntry = bundle.entry
    ledger_stub = _ledger_stub(ctx)

    dye_fidelity, clipped_epochs = sequence_tint_restoration(
        ledger_stub,
        list(bundle.dye_reformulations),
        list(bundle.epochs),
        bundle.school_recitals,
        ctx.blend["dye_penalty_rate"],
        dye_seed,
    )

    lineage = walk_weaver_trust(
        entry.weaver_id,
        master_weavers["mentor_of"],
        master_weavers,
        entry.completion_year,
    )

    coverage = school_continuity_span(
        clipped_epochs,
        bundle.loom_letters,
        bundle.sales,
        merchant_permits_relay,
        ctx.replay_floor,
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
''')

Path("/app/heddle_bind/catalog_resolver.py").write_text('''from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PanelEntry:
    panel_id: str
    canonical_id: str
    weaver_id: str
    completion_year: int


def resolve_panel_entry(panel_id: str, catalog: dict[str, Any]) -> PanelEntry:
    row = catalog[panel_id]
    if "alias_of" in row:
        canonical = str(row["alias_of"])
        base = catalog[canonical]
    else:
        canonical = panel_id
        base = row
    return PanelEntry(
        panel_id=panel_id,
        canonical_id=canonical,
        weaver_id=str(base["weaver_id"]),
        completion_year=int(base.get("completion_year", 1900)),
    )
''')

Path("/app/heddle_bind/coeff_loader.py").write_text('''from __future__ import annotations

from pathlib import Path
from typing import Any


def load_genealogy_blend(
    config_dir: Path | None = None,
    section_name: str = "genealogy_blend",
) -> dict[str, float]:
    config_dir = config_dir or Path("/app/config")
    weights = config_dir / "weights.toml"
    blend: dict[str, float] = {}
    in_section = False
    header = f"[{section_name}]"
    for line in weights.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == header
            continue
        if not in_section or "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        blend[key.strip()] = float(value.strip())
    return blend


def letter_weight(coverage: float, blend: dict[str, Any]) -> float:
    floor = float(blend["letter_floor"])
    span = float(blend["letter_span"])
    return floor + span * (coverage / 100.0)
''')

Path("/app/heddle_bind/epoch_bound.py").write_text('''from __future__ import annotations

from typing import Any


def clip_bundle_timeline(
    bundle: dict[str, Any],
    dye_reformulations: list[dict[str, Any]],
    epochs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    snapshot = bundle.get("genealogy_snapshot") or {}
    as_of = snapshot.get("as_of_year")
    if as_of is None:
        return list(dye_reformulations), list(epochs)

    as_of_year = int(as_of)
    clipped_dye_reformulations = [row for row in dye_reformulations if int(row["year"]) <= as_of_year]
    clipped_epochs: list[dict[str, Any]] = []
    for epoch in epochs:
        if int(epoch["from_year"]) > as_of_year:
            continue
        clipped_epochs.append(
            {**epoch, "to_year": min(int(epoch["to_year"]), as_of_year)}
        )
    return clipped_dye_reformulations, clipped_epochs
''')

Path("/app/atelier_chain/lineage_map.py").write_text('''from __future__ import annotations

from typing import Any


def compile_lineage_map(
    mentor_of: dict[str, str],
    lineage_epochs: dict[str, Any],
    completion_year: int,
) -> dict[str, str]:
    compiled: dict[str, str] = {}
    for child, parent in mentor_of.items():
        epoch = lineage_epochs.get(child, {})
        active_from = int(epoch.get("active_from_year", 0))
        if completion_year >= active_from:
            compiled[child] = parent
    return compiled
''')

Path("/app/atelier_chain/weaver_trust.py").write_text('''from __future__ import annotations

from typing import Any

from atelier_chain.lineage_map import compile_lineage_map


def walk_weaver_trust(
    weaver_id: str,
    mentor_of: dict[str, str],
    master_weavers: dict[str, Any],
    completion_year: int,
) -> float:
    active = compile_lineage_map(
        mentor_of,
        master_weavers.get("lineage_epochs", {}),
        completion_year,
    )
    weight = 1.0
    current = weaver_id
    visited: set[str] = set()
    while current in active:
        if current in visited:
            break
        visited.add(current)
        profile = master_weavers.get(current, {})
        weight *= float(profile.get("thread_trust", 1.0))
        current = active[current]
    return weight
''')

Path("/app/chroma_record/recipe_gate.py").write_text('''from __future__ import annotations

from typing import Any


def gated_reformulations(
    dye_reformulations: list[dict[str, Any]],
    epochs: list[dict[str, Any]],
    school_recitals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recital_years = [int(row["year"]) for row in school_recitals]
    if not recital_years:
        return []
    eligible_years: set[int] = set()
    for epoch in epochs:
        if epoch.get("export_eligible", True):
            eligible_years.update(
                range(int(epoch["from_year"]), int(epoch["to_year"]) + 1)
            )
    scoped: list[dict[str, Any]] = []
    for row in dye_reformulations:
        year = int(row["year"])
        if year not in eligible_years:
            continue
        if not any(recital_year <= year for recital_year in recital_years):
            continue
        scoped.append(row)
    return scoped
''')

Path("/app/shed_weave/registry_cache.py").write_text('''from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shed_weave.digest_materializer import merge_dye_overlays
from shed_weave.loader import load_registry


def load_registry(directory: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in sorted(directory.glob("*.json")):
        merged.update(json.loads(path.read_text()))
    return merged


def load_dye_reformulations(data_root: Path) -> dict[str, Any]:
    merged = load_registry(data_root / "dye_reformulations")
    return merge_dye_overlays(merged, data_root)
''')

Path("/app/chroma_record/fidelity_curve.py").write_text('''from __future__ import annotations

from typing import Any


def compound_dye_fidelity(
    dye_reformulations: list[dict[str, Any]],
    penalty_rate: float,
    dye_seed: float = 1.0,
) -> float:
    factor = dye_seed
    for event in sorted(dye_reformulations, key=lambda row: int(row["year"])):
        if event.get("reset_drift"):
            factor = 1.0
            continue
        factor *= 1.0 - penalty_rate * float(event["severity"])
    return max(0.0, factor)
''')

Path("/app/relay_cordage/transfer_gate.py").write_text('''from __future__ import annotations

from typing import Any


def merchant_permits_relay(
    sales: list[dict[str, Any]],
    transfer_year: int,
    seller: str,
    buyer: str,
) -> bool:
    for sale in sales:
        if (
            int(sale["year"]) == transfer_year
            and sale["seller"] == seller
            and sale["buyer"] == buyer
            and sale.get("kind") == "arms_length"
        ):
            return True
    return False
''')

Path("/app/relay_cordage/route_span.py").write_text('''from __future__ import annotations

from collections.abc import Callable
from typing import Any


def slice_custody_epochs(
    epochs: list[dict[str, Any]],
    replay_floor: int,
) -> list[dict[str, Any]]:
    if replay_floor <= 1:
        return list(epochs)
    skip = replay_floor - 1
    if skip >= len(epochs):
        return []
    return epochs[skip:]


def _owner_for_year(epochs: list[dict[str, Any]], year: int) -> str | None:
    for epoch in epochs:
        if int(epoch["from_year"]) <= year <= int(epoch["to_year"]):
            return str(epoch["owner_id"])
    return None


def _prev_owner_at_transfer(epochs: list[dict[str, Any]], year: int) -> str | None:
    for epoch in epochs:
        if int(epoch["from_year"]) == year:
            prior = [item for item in epochs if int(item["to_year"]) == year - 1]
            if prior:
                return prior[0]["owner_id"]
    return None


def _cert_valid(cert: dict[str, Any], year: int) -> bool:
    return int(cert["issued_year"]) <= year <= int(cert["expires_year"])


def school_continuity_span(
    epochs: list[dict[str, Any]],
    certs: list[dict[str, Any]],
    sales: list[dict[str, Any]],
    relay_check: Callable[[list[dict[str, Any]], int, str, str], bool],
    replay_floor: int = 0,
) -> float:
    epochs = slice_custody_epochs(epochs, replay_floor)
    if not epochs:
        return 0.0
    start = min(int(epoch["from_year"]) for epoch in epochs)
    end = max(int(epoch["to_year"]) for epoch in epochs)
    span = end - start + 1
    if span <= 0:
        return 0.0

    covered = 0
    for year in range(start, end + 1):
        owner = _owner_for_year(epochs, year)
        if owner is None:
            continue
        ok = False
        for cert in certs:
            if cert["holder"] == owner and _cert_valid(cert, year):
                ok = True
                break
        if not ok:
            prev = _prev_owner_at_transfer(epochs, year)
            if prev:
                for cert in certs:
                    if (
                        cert["holder"] == prev
                        and cert.get("transfers_with_sale")
                        and _cert_valid(cert, year)
                        and relay_check(sales, year, prev, owner)
                    ):
                        ok = True
                        break
        if ok:
            covered += 1
    return 100.0 * covered / span
''')
PY

python3 << 'PY'
from pathlib import Path

Path("/app/shed_weave/phase_runner.py").write_text('''from __future__ import annotations

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
    return run_panel_phases(bundle, ctx, master_weavers, dye_seed=dye_seed)
''')

Path("/app/shed_weave/session_anchor.py").write_text('''from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shed_weave.digest_materializer import build_catalog_snapshot, registry_digest
from shed_weave.loader import data_root
from heddle_bind.coeff_loader import load_genealogy_blend
from shed_weave.trace_profile import active_policy_family, remember_trace_blend


@dataclass(frozen=True)
class CompileContext:
    bundle_id: str
    policy_family: str
    snapshot_as_of: int | None
    blend: dict[str, float]
    network_seal: str
    replay_floor: int = 0


def _policy_family(bundle: dict[str, Any]) -> str:
    family = bundle.get("policy_family")
    if family is None:
        return "standard"
    return str(family)


def _snapshot_as_of(bundle: dict[str, Any]) -> int | None:
    snapshot = bundle.get("genealogy_snapshot") or {}
    as_of = snapshot.get("as_of_year")
    if as_of is None:
        return None
    return int(as_of)


def build_compile_context(
    bundle: dict[str, Any],
    catalogs: dict[str, Any],
    config_dir: Path,
) -> CompileContext:
    family = _policy_family(bundle)
    section = "genealogy_blend" if family == "standard" else f"genealogy_blend.{family}"
    blend = load_genealogy_blend(config_dir, section_name=section)
    blend = remember_trace_blend(blend, family)
    family = active_policy_family(family)
    digest_catalogs = build_catalog_snapshot(data_root(), include_overlays=True)
    digest = registry_digest(digest_catalogs)
    snapshot = _snapshot_as_of(bundle)
    snapshot_token = str(snapshot) if snapshot is not None else "None"
    panel_manifest = ",".join(str(entry["panel_id"]) for entry in bundle.get("panels", []))
    manifest_digest = hashlib.sha256(panel_manifest.encode()).hexdigest()[:8]
    stamp_parts = [
        bundle["bundle_id"],
        family,
        snapshot_token,
        digest,
        manifest_digest,
    ]
    network_seal = hashlib.sha256("|".join(stamp_parts).encode()).hexdigest()[:24]
    return CompileContext(
        bundle_id=str(bundle["bundle_id"]),
        policy_family=family,
        snapshot_as_of=snapshot,
        blend=blend,
        network_seal=network_seal,
    )
''')

slice_mod = Path("/app/shed_weave/registry_slice.py")
text = slice_mod.read_text()
text = text.replace(
    "    lookup_key = entry.panel_id\n"
    "    canonical = entry.canonical_id\n"
    "    return PanelBundle(\n"
    "        entry=entry,\n"
    "        dye_reformulations=list(catalogs[\"dye_reformulations\"].get(lookup_key, [])),\n"
    "        epochs=list(catalogs[\"export_routes\"].get(lookup_key, [])),\n",
    "    canonical = entry.canonical_id\n"
    "    return PanelBundle(\n"
    "        entry=entry,\n"
    "        dye_reformulations=list(catalogs[\"dye_reformulations\"].get(canonical, [])),\n"
    "        epochs=list(catalogs[\"export_routes\"].get(canonical, [])),\n",
)
text = text.replace(
    "        school_recitals=list(catalogs[\"school_recitals\"].get(lookup_key, [])),\n",
    "        school_recitals=list(catalogs[\"school_recitals\"].get(canonical, [])),\n",
)
slice_mod.write_text(text)

cli = Path("/app/shed_weave/cli.py")
text = cli.read_text()
text = text.replace(
    "        if os.environ.get(\"TRACE_RESUME\") == \"1\":\n"
    "            report = read_journal()\n"
    "            if report is None:\n"
    "                report = build_pattern_genealogy(args.bundle)\n",
    "        if os.environ.get(\"TRACE_RESUME\") == \"1\":\n"
    "            journal = read_journal()\n"
    "            fresh = build_pattern_genealogy(args.bundle)\n"
    "            if journal is None:\n"
    "                report = fresh\n"
    "            elif journal.get(\"network_seal\") == fresh.get(\"network_seal\"):\n"
    "                report = journal\n"
    "            else:\n"
    "                report = fresh\n",
)
cli.write_text(text)
PY

for bundle in /app/data/bundles/*.json; do
  case "$bundle" in
    */index.json) continue ;;
  esac
  python3 -m shed_weave.cli trace --bundle "$bundle" --out /app/output/pattern_genealogy.json
done

echo "Oracle silk pattern genealogy trace pipeline repairs applied."
