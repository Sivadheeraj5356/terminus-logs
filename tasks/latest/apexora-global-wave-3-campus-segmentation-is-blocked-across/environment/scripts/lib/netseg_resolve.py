#!/usr/bin/env python3
"""SegmentFirst transitive resolution spine.

Every function here is the public, documented derivation used by the pipeline
and mirrored by the verifier. Formulas live in docs/OPERATIONS.md
(dependency spine) and docs/segmentation_contract.md.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

OPS_VLAN_LO = 2001
OPS_VLAN_HI = 2180  # inclusive
LEGACY_VRF = "VRF-CORP"
CANONICAL_WAN_VRF = "CORP-IT"
LEGACY_ACL = {
    "ACL-INSIDE-ANY",
    "ACL-EDGE-LEGACY",
    "OG-FLAT-USER",
    "OG-FLAT-FINANCE",
    "OG-FLAT-SERVER",
}
ACTIVE_HOOK = "services/hooks/post-validate.sh"
LEGACY_HOOK = "legacy/hooks/pre-validate-legacy.sh"
REGIONAL_ORDER = ["amer", "emea", "apac"]
CANARY_ANCHOR = "dist-hq-dal-main-01"
SPINE = (
    "vlan-check",
    "trunk-check",
    "acl-check",
    "render",
    "wave-plan",
    "rollback-audit",
    "evidence",
)


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def operations_vlan_range() -> set[int]:
    """Authoritative VLAN ID set from docs/OPERATIONS.md (2001 through 2180)."""
    return set(range(OPS_VLAN_LO, OPS_VLAN_HI + 1))


def catalog_vlan_ids(env: Path) -> set[int]:
    catalog = load_yaml(env / "vlans/catalog.yaml")
    return {int(v["id"]) for v in catalog.get("vlans", [])}


def campus_vlan_union(env: Path) -> set[int]:
    ids: set[int] = set()
    for path in sorted((env / "vlans/campuses").glob("*.yaml")):
        doc = load_yaml(path)
        for row in doc.get("vlans", []) or []:
            ids.add(int(row["id"]))
    return ids


def legacy_map_targets(env: Path) -> set[int]:
    doc = load_yaml(env / "vlans/legacy_id_map.yaml")
    return {int(v) for v in (doc.get("legacy_to_canonical") or {}).values()}


def legacy_map_keys(env: Path) -> set[int]:
    doc = load_yaml(env / "vlans/legacy_id_map.yaml")
    return {int(k) for k in (doc.get("legacy_to_canonical") or {}).keys()}


def catalog_legacy_ids(env: Path) -> set[int]:
    catalog = load_yaml(env / "vlans/catalog.yaml")
    return {int(v["legacy_id"]) for v in catalog.get("vlans", []) if v.get("legacy_id") is not None}


def resolve_canonical_vlans(env: Path) -> dict[str, Any]:
    """Derive the canonical VLAN set from multiple authoritative sources.

    canonical_ids = operations_range ∩ catalog_ids ∩ campus_union

    Consistency (all must hold or source_drift is non-empty):
    - every catalog.legacy_id is a key in vlans/legacy_id_map.yaml
    - every legacy_id_map target is in canonical_ids
    - campus_union equals catalog_ids
    """
    ops = operations_vlan_range()
    catalog = catalog_vlan_ids(env)
    campuses = campus_vlan_union(env)
    legacy_targets = legacy_map_targets(env)
    legacy_keys = legacy_map_keys(env)
    cat_legacy = catalog_legacy_ids(env)

    canonical = ops & catalog & campuses
    drift: list[str] = []
    if catalog != campuses:
        drift.append("campus_catalog_mismatch")
    if cat_legacy - legacy_keys:
        drift.append("catalog_legacy_unmapped")
    if legacy_targets - canonical:
        drift.append("legacy_target_outside_canonical")
    if canonical != ops or len(canonical) != len(ops):
        drift.append("canonical_incomplete")

    return {
        "canonical_ids": canonical,
        "vlan_catalog_count": len(canonical),
        "source_drift": sorted(drift),
        "resolved_from": [
            "docs/OPERATIONS.md#authoritative-vlan-range",
            "vlans/catalog.yaml",
            "vlans/campuses/*.yaml",
            "vlans/legacy_id_map.yaml",
        ],
    }


def campus_region_map(env: Path) -> dict[str, str]:
    doc = load_yaml(env / "inventory/campus_index.yaml")
    return {str(c["id"]): str(c["region"]) for c in doc.get("campuses", [])}


def vrf_catalog_names(env: Path) -> set[str]:
    cat = load_yaml(env / "vrfs/catalog.yaml")
    return set((cat.get("vrfs") or {}).keys())


def regional_vrf_names(env: Path, region: str) -> set[str]:
    path = env / "vrfs/campus_route_targets" / f"{region}.yaml"
    if not path.is_file():
        return set()
    doc = load_yaml(path)
    return {str(row["vrf"]) for row in doc.get("route_targets", []) or []}


def resolve_vrfs(env: Path) -> dict[str, Any]:
    """Derive permitted VRFs per region: policy catalog ∩ regional route-target overrides."""
    policy = vrf_catalog_names(env)
    by_region: dict[str, list[str]] = {}
    for region in REGIONAL_ORDER:
        resolved = sorted(policy & regional_vrf_names(env, region))
        by_region[region] = resolved
    return {
        "by_region": by_region,
        "wan_edge_canonical": CANONICAL_WAN_VRF,
        "resolved_from": [
            "vrfs/catalog.yaml",
            "vrfs/campus_route_targets/{amer,emea,apac}.yaml",
            "inventory/campus_index.yaml",
        ],
    }


def active_acl_policies(env: Path) -> list[dict[str, Any]]:
    cat = load_yaml(env / "acl/catalog.yaml")
    return [p for p in cat.get("policies", []) if p.get("status") == "active"]


def resolve_acls_from_vrfs(env: Path, vrf_resolution: dict[str, Any] | None = None) -> dict[str, Any]:
    """Allowed ACL names per region = active policies whose vrf ∈ resolved regional VRFs."""
    vrf_resolution = vrf_resolution or resolve_vrfs(env)
    policies = active_acl_policies(env)
    by_region: dict[str, list[str]] = {}
    for region, vrfs in vrf_resolution["by_region"].items():
        allowed = sorted({str(p["name"]) for p in policies if str(p.get("vrf", "")) in set(vrfs)})
        by_region[region] = allowed
    return {
        "by_region": by_region,
        "policy_catalog_count": len(policies),
        "active_names": sorted({str(p["name"]) for p in policies}),
        "resolved_from": [
            "resolved VRFs (policy ∩ regional overrides)",
            "acl/catalog.yaml (status=active)",
        ],
    }


def trunk_link_count(env: Path) -> int:
    """Count declared trunk links under trunks/links/ (not a hidden constant)."""
    return len(list((env / "trunks/links").glob("*.yaml")))


def devices(env: Path) -> list[dict[str, Any]]:
    inv = load_yaml(env / "inventory/device_inventory.yaml")
    return sorted(inv.get("devices", []), key=lambda d: d["hostname"])


def in_scope(row: dict[str, Any]) -> bool:
    return row.get("migration_state") in {"legacy", "partial"}


def validation_scope_hostnames(env: Path) -> list[str]:
    scope = load_yaml(env / "inventory/wave3_validation_scope.yaml")
    return list(scope.get("hostnames", []))


def device_region(env: Path, row: dict[str, Any], campus_regions: dict[str, str] | None = None) -> str:
    campus_regions = campus_regions or campus_region_map(env)
    return campus_regions.get(str(row.get("campus_id", "")), "")


def device_running_conf(env: Path, hostname: str, role: str) -> Path | None:
    if role == "access":
        p = env / "switches/access" / hostname / "running.conf"
    elif role == "distribution":
        p = env / "switches/distribution" / hostname / "running.conf"
    elif role == "core":
        p = env / "switches/core" / hostname / "running.conf"
    elif role == "wan_edge":
        for p in (env / "routers").rglob(hostname):
            if p.is_dir():
                rc = p / "running.conf"
                if rc.is_file():
                    return rc
        return None
    else:
        return None
    return p if p.is_file() else None


def read_conf(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def acl_refs(text: str) -> set[str]:
    refs = set(re.findall(r"ip access-group (\S+)", text))
    refs.update(re.findall(r"object-group (\S+)", text))
    return refs


def trunk_policy_mode(env: Path) -> str:
    doc = load_yaml(env / "interfaces/trunk/trunk_policy.yaml")
    policies = doc.get("policies") or {}
    access = policies.get("access_to_dist") or {}
    return str(access.get("mode", "selective"))


def trunk_live_violations(conf: str, role: str, *, policy_mode: str = "selective") -> list[str]:
    violations: list[str] = []
    if policy_mode == "selective" and re.search(r"switchport trunk allowed vlan all\b", conf):
        violations.append("trunk_all_vlans")
    if role == "access" and re.search(r"^interface Vlan\d+\n(?:.*\n)*?^\s+ip address ", conf, re.M):
        violations.append("access_layer_svi")
    if re.search(r"^\s*ip default-gateway ", conf, re.M):
        violations.append("access_layer_gateway")
    if re.search(r"3001-3099", conf):
        violations.append("over_permissive_allowed_vlan")
    return violations


def load_stage_output(out_root: Path, name: str) -> dict[str, Any] | None:
    path = out_root / name
    if not path.is_file():
        return None
    return load_json(path)


def rendered_hostnames(out_root: Path) -> set[str]:
    rendered = out_root / "rendered"
    if not rendered.is_dir():
        return set()
    return {p.stem for p in rendered.glob("*.conf")}
