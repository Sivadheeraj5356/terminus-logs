from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shed_weave.digest_materializer import build_catalog_snapshot, registry_digest
from shed_weave.loader import data_root
from shed_weave.trace_profile import active_policy_family, remember_trace_blend
from heddle_bind.coeff_loader import load_genealogy_blend


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
    section = "genealogy_blend"
    blend = load_genealogy_blend(config_dir, section_name=section)
    blend = remember_trace_blend(blend, family)
    family = active_policy_family(family)
    digest_catalogs = build_catalog_snapshot(data_root(), include_overlays=False)
    digest = registry_digest(digest_catalogs)
    stamp_parts = [
        bundle["bundle_id"],
        family,
        str(_snapshot_as_of(bundle)),
        digest,
    ]
    network_seal = hashlib.sha256("|".join(stamp_parts).encode()).hexdigest()[:24]
    return CompileContext(
        bundle_id=str(bundle["bundle_id"]),
        policy_family=family,
        snapshot_as_of=_snapshot_as_of(bundle),
        blend=blend,
        network_seal=network_seal,
    )
