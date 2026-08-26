"""Verifier invariants — sealed golden contracts plus focused live-config checks.

Immutable baselines (migration map, validation scope, VLAN catalog size) live in
helpers.py. This module checks documented invariants from OPERATIONS.md and
ROLLBACK.md against declarative configuration and pipeline exports; it does not
recompute full expected pipeline artifacts.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from helpers import (
    DEVICE_COUNT,
    ENV,
    EXPECTED_MIGRATION_STATE,
    EXPECTED_VALIDATION_SCOPE,
    EXPECTED_VLAN_IDS,
    IN_SCOPE_COUNT,
    OUTPUT,
    POLICY_CATALOG_COUNT,
    TRUNK_LINK_COUNT,
    VALIDATION_SCOPE_COUNT,
    VLAN_CATALOG_COUNT,
)

LEGACY_VRF = "VRF-CORP"
CANONICAL_VRF = "CORP-IT"
LEGACY_ACL = {
    "ACL-INSIDE-ANY",
    "ACL-EDGE-LEGACY",
    "OG-FLAT-USER",
    "OG-FLAT-FINANCE",
    "OG-FLAT-SERVER",
}
LEGACY_HOOK = "legacy/hooks/pre-validate-legacy.sh"
ACTIVE_HOOK = "services/hooks/post-validate.sh"
REGIONAL_ORDER = ["amer", "emea", "apac"]
CANARY_ANCHOR = "dist-hq-dal-main-01"
OPS_VLAN_LO = 2001
OPS_VLAN_HI = 2180

M1_SECTION_IDS = {
    "policy-source-precedence-2026",
    "vlan-assignment-standards-2026",
    "vlan-identity",
    "vlan-naming-standard-2026",
    "vrf-policy-2026",
    "device-hostname-standard-2026",
}

SPINE = (
    "vlan-check",
    "trunk-check",
    "acl-check",
    "render",
    "wave-plan",
    "rollback-audit",
    "evidence",
)


def validation_command_for(hostname: str) -> str:
    return f"{ACTIVE_HOOK} {hostname}"


def parse_validation_command(command: str) -> list[str] | None:
    """Return exactly two tokens (hook, hostname) or None when malformed."""
    if not command or not command.strip():
        return None
    tokens = command.strip().split()
    if len(tokens) != 2:
        return None
    return tokens


def validation_command_matches(hostname: str, command: str) -> bool:
    """Public rollback contract: hook followed by hostname as its sole argument."""
    tokens = parse_validation_command(command)
    if tokens is None:
        return False
    hook, host = tokens
    return hook == ACTIVE_HOOK and host == hostname


def evaluation_as_of() -> str:
    return str(load_yaml("data/evaluation_clock.json")["as_of"])


def clear_caches() -> None:
    _load_yaml.cache_clear()


@lru_cache(maxsize=64)
def _load_yaml(path_str: str) -> Any:
    return yaml.safe_load(Path(path_str).read_text(encoding="utf-8"))


def load_yaml(rel: str) -> Any:
    return _load_yaml(str(ENV / rel))


def active_section_ids() -> list[str]:
    precedence = load_yaml("configs/assembly/source_precedence.yaml")
    return sorted(str(s) for s in precedence.get("active_sections", []))


def device_rows() -> list[dict[str, Any]]:
    inv = load_yaml("inventory/device_inventory.yaml")
    return sorted(inv.get("devices", []), key=lambda d: d["hostname"])


def hostnames() -> list[str]:
    return [d["hostname"] for d in device_rows()]


def in_scope(row: dict[str, Any]) -> bool:
    return EXPECTED_MIGRATION_STATE.get(row["hostname"]) in {"legacy", "partial"}


def in_scope_devices() -> list[dict[str, Any]]:
    return [d for d in device_rows() if in_scope(d)]


def in_scope_hostnames() -> list[str]:
    return sorted(d["hostname"] for d in in_scope_devices())


def in_scope_access_hostnames() -> list[str]:
    return sorted(d["hostname"] for d in in_scope_devices() if d["role"] == "access")


def in_scope_wan_edge_hostnames() -> list[str]:
    return sorted(d["hostname"] for d in in_scope_devices() if d["role"] == "wan_edge")


def validation_scope_hostnames_static() -> list[str]:
    return list(EXPECTED_VALIDATION_SCOPE)


def validation_scope_devices() -> list[dict[str, Any]]:
    by_name = {d["hostname"]: d for d in device_rows()}
    return [by_name[h] for h in EXPECTED_VALIDATION_SCOPE if h in by_name]


def validation_scope_hostnames() -> list[str]:
    return validation_scope_hostnames_static()


def inventory_migration_state_map() -> dict[str, str]:
    return {d["hostname"]: str(d.get("migration_state", "")) for d in device_rows()}


def inventory_validation_scope_hosts() -> list[str]:
    scope = load_yaml("inventory/wave3_validation_scope.yaml")
    return list(scope.get("hostnames", []))


def device_running_conf(hostname: str, role: str) -> Path | None:
    if role == "access":
        p = ENV / "switches/access" / hostname / "running.conf"
    elif role == "distribution":
        p = ENV / "switches/distribution" / hostname / "running.conf"
    elif role == "core":
        p = ENV / "switches/core" / hostname / "running.conf"
    elif role == "wan_edge":
        for p in (ENV / "routers").rglob(hostname):
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


def legacy_vlan_on_access(text: str) -> bool:
    for m in re.finditer(r"switchport access vlan (\d+)", text):
        vid = int(m.group(1))
        if 101 <= vid <= 180:
            return True
    return False


def trunk_all(text: str) -> bool:
    return bool(re.search(r"switchport trunk allowed vlan all\b", text))


def access_svi_present(text: str) -> bool:
    return bool(re.search(r"^interface Vlan\d+\n(?:.*\n)*?^\s+ip address ", text, re.M))


def acl_refs(text: str) -> set[str]:
    refs = set(re.findall(r"ip access-group (\S+)", text))
    refs.update(re.findall(r"object-group (\S+)", text))
    return refs


def operations_vlan_range() -> set[int]:
    return set(range(OPS_VLAN_LO, OPS_VLAN_HI + 1))


def catalog_vlan_ids() -> set[int]:
    catalog = load_yaml("vlans/catalog.yaml")
    return {int(v["id"]) for v in catalog.get("vlans", [])}


def campus_vlan_union() -> set[int]:
    ids: set[int] = set()
    for path in sorted((ENV / "vlans/campuses").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for row in doc.get("vlans", []) or []:
            ids.add(int(row["id"]))
    return ids


def legacy_map_targets() -> set[int]:
    doc = load_yaml("vlans/legacy_id_map.yaml")
    return {int(v) for v in (doc.get("legacy_to_canonical") or {}).values()}


def legacy_map_keys() -> set[int]:
    doc = load_yaml("vlans/legacy_id_map.yaml")
    return {int(k) for k in (doc.get("legacy_to_canonical") or {}).keys()}


def catalog_legacy_ids() -> set[int]:
    catalog = load_yaml("vlans/catalog.yaml")
    return {int(v["legacy_id"]) for v in catalog.get("vlans", []) if v.get("legacy_id") is not None}


def resolve_canonical_vlans() -> dict[str, Any]:
    """canonical = ops_range ∩ catalog ∩ campus_union, plus legacy-map consistency."""
    ops = operations_vlan_range()
    catalog = catalog_vlan_ids()
    campuses = campus_vlan_union()
    legacy_targets = legacy_map_targets()
    legacy_keys = legacy_map_keys()
    cat_legacy = catalog_legacy_ids()
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


def campus_region_map() -> dict[str, str]:
    doc = load_yaml("inventory/campus_index.yaml")
    return {str(c["id"]): str(c["region"]) for c in doc.get("campuses", [])}


def resolve_vrfs() -> dict[str, Any]:
    cat = load_yaml("vrfs/catalog.yaml")
    policy = set((cat.get("vrfs") or {}).keys())
    by_region: dict[str, list[str]] = {}
    for region in REGIONAL_ORDER:
        path = ENV / "vrfs/campus_route_targets" / f"{region}.yaml"
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
        regional = {str(row["vrf"]) for row in doc.get("route_targets", []) or []}
        by_region[region] = sorted(policy & regional)
    return {
        "by_region": by_region,
        "wan_edge_canonical": CANONICAL_VRF,
        "resolved_from": [
            "vrfs/catalog.yaml",
            "vrfs/campus_route_targets/{amer,emea,apac}.yaml",
            "inventory/campus_index.yaml",
        ],
    }


def resolve_acls_from_vrfs(vrf_resolution: dict[str, Any] | None = None) -> dict[str, Any]:
    vrf_resolution = vrf_resolution or resolve_vrfs()
    cat = load_yaml("acl/catalog.yaml")
    policies = [p for p in cat.get("policies", []) if p.get("status") == "active"]
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


def trunk_link_count() -> int:
    return len(list((ENV / "trunks/links").glob("*.yaml")))


def trunk_policy_mode() -> str:
    doc = load_yaml("interfaces/trunk/trunk_policy.yaml")
    policies = doc.get("policies") or {}
    access = policies.get("access_to_dist") or {}
    return str(access.get("mode", "selective"))


def device_region(row: dict[str, Any], campus_regions: dict[str, str] | None = None) -> str:
    campus_regions = campus_regions or campus_region_map()
    return campus_regions.get(str(row.get("campus_id", "")), "")


def authoritative_precedence() -> bool:
    precedence = load_yaml("configs/assembly/source_precedence.yaml")
    return not precedence.get("consult_legacy_when_present", True)


def retired_vlan_families() -> list[str]:
    precedence = load_yaml("configs/assembly/source_precedence.yaml")
    return sorted(precedence.get("retired_vlan_families", []))


def canonical_vlan_ids() -> set[int]:
    """Resolved canonical set; must equal verifier golden EXPECTED_VLAN_IDS when consistent."""
    resolved = resolve_canonical_vlans()
    if resolved["source_drift"]:
        return set()
    return set(resolved["canonical_ids"])


def active_acl_names() -> set[str]:
    return set(resolve_acls_from_vrfs()["active_names"])


def access_vlan_assignments_ok(hostname: str) -> bool:
    conf = read_conf(device_running_conf(hostname, "access"))
    allowed = canonical_vlan_ids()
    if not allowed:
        return False
    for m in re.finditer(r"switchport access vlan (\d+)", conf):
        vid = int(m.group(1))
        if vid not in allowed or 101 <= vid <= 180:
            return False
    meta = ENV / "switches/access" / hostname / "vlan.local.yaml"
    if meta.is_file() and load_yaml(str(meta.relative_to(ENV))).get("duplicate_vlan_conflict"):
        return False
    return True


def vrf_binding_ok(hostname: str) -> bool:
    conf = read_conf(device_running_conf(hostname, "wan_edge"))
    return LEGACY_VRF not in conf


def gateway_bindings() -> list[dict[str, Any]]:
    return load_yaml("interfaces/gateway/gateway_bindings.yaml").get("bindings", [])


def gateway_on_distribution(bind: dict[str, Any]) -> bool:
    primary = bind["primary"]
    vlan_id = bind["vlan_id"]
    vip = bind["vip"]
    base = ENV / "switches/distribution" / primary
    candidates = [
        base / "running.conf",
        base / "svi.conf",
        base / "interfaces" / f"Vlan{vlan_id}.conf",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        conf = path.read_text(encoding="utf-8")
        if f"interface Vlan{vlan_id}" in conf and vip in conf:
            return True
        if f"Vlan{vlan_id}" in conf and vip in conf:
            return True
    return False


def config_authoritative_m1() -> bool:
    if not authoritative_precedence():
        return False
    if resolve_canonical_vlans()["source_drift"]:
        return False
    if canonical_vlan_ids() != set(EXPECTED_VLAN_IDS):
        return False
    for row in in_scope_devices():
        if row["role"] == "access" and not access_vlan_assignments_ok(row["hostname"]):
            return False
        if row["role"] == "wan_edge" and not vrf_binding_ok(row["hostname"]):
            return False
    return True


def trunk_live_violations(conf: str, role: str) -> list[str]:
    violations: list[str] = []
    mode = trunk_policy_mode()
    if mode == "selective" and trunk_all(conf):
        violations.append("trunk_all_vlans")
    if role == "access" and access_svi_present(conf):
        violations.append("access_layer_svi")
    if re.search(r"^\s*ip default-gateway ", conf, re.M):
        violations.append("access_layer_gateway")
    if re.search(r"3001-3099", conf):
        violations.append("over_permissive_allowed_vlan")
    return violations


def trunk_seed_by_host() -> dict[str, list[str]]:
    seed_rows = load_yaml("trunks/violations_seed.yaml").get("violations") or []
    seed_by_host: dict[str, list[str]] = {}
    for entry in seed_rows:
        device = str(entry.get("device", ""))
        issue = str(entry.get("issue", ""))
        if device and issue:
            seed_by_host.setdefault(device, []).append(issue)
    return seed_by_host


def trunk_violations(conf: str, role: str, hostname: str | None = None) -> list[str]:
    violations = trunk_live_violations(conf, role)
    if hostname is None:
        return violations
    for issue in trunk_seed_by_host().get(hostname, []):
        if issue not in violations:
            violations.append(issue)
    return violations


def trunk_authoritative() -> bool:
    seed = load_yaml("trunks/violations_seed.yaml")
    if seed.get("violations"):
        return False
    for row in in_scope_devices():
        conf = read_conf(device_running_conf(row["hostname"], row["role"]))
        violations = trunk_violations(conf, row["role"], row["hostname"])
        if violations:
            return False
    return True


def config_authoritative_m2() -> bool:
    return config_authoritative_m1() and trunk_authoritative()


def acl_authoritative() -> bool:
    vrf_res = resolve_vrfs()
    acl_res = resolve_acls_from_vrfs(vrf_res)
    active = set(acl_res["active_names"])
    campus_regions = campus_region_map()
    for row in validation_scope_devices():
        hostname = row["hostname"]
        region = device_region(row, campus_regions)
        allowed = set(acl_res["by_region"].get(region, []))
        conf = read_conf(device_running_conf(hostname, row["role"]))
        refs = acl_refs(conf)
        for ref in refs:
            if ref in LEGACY_ACL or (ref.startswith("OG-FLAT-") and ref not in active):
                return False
            if ref.startswith("SEG-") and ref not in active:
                return False
            if ref.startswith("SEG-") and ref in active and ref not in allowed:
                return False
        if row["role"] == "wan_edge":
            if LEGACY_VRF in conf:
                return False
            if CANONICAL_VRF not in vrf_res["by_region"].get(region, []):
                return False
        if in_scope(row):
            conf_t = read_conf(device_running_conf(hostname, row["role"]))
            if trunk_violations(conf_t, row["role"], hostname):
                return False
    return True


def legacy_hooks_present() -> bool:
    if (ENV / LEGACY_HOOK).is_file():
        return True
    canary = load_yaml("deployment/canary/groups.yaml")
    hook = canary.get("groups", [{}])[0].get("gate", {}).get("validation_hook", "")
    wave = load_yaml("deployment/waves/wave_3.yaml")
    return LEGACY_HOOK in hook or bool(wave.get("legacy_hooks_present"))


def rendered_hostnames() -> set[str]:
    rendered = OUTPUT / "rendered"
    if not rendered.is_dir():
        return set()
    return {p.stem for p in rendered.glob("*.conf")}


def wave_authoritative() -> bool:
    wave = load_yaml("deployment/waves/wave_3.yaml")
    if not wave.get("canary_first"):
        return False
    if wave.get("regional_order") != REGIONAL_ORDER:
        return False
    if legacy_hooks_present():
        return False
    phases = wave.get("phases", [])
    if not phases or phases[0].get("phase_id") != "canary":
        return False
    phased: set[str] = set()
    for phase in phases:
        phased.update(phase.get("devices", []))
    scope = set(validation_scope_hostnames())
    if not scope <= phased:
        return False
    # Transitive: in-scope validation hosts must have rendered bundles when outputs exist.
    rendered = rendered_hostnames()
    if rendered:
        in_scope_names = set(in_scope_hostnames())
        if (scope & in_scope_names) - rendered:
            return False
    campus_regions = campus_region_map()
    by_name = {d["hostname"]: d for d in device_rows()}
    for phase in phases:
        phase_id = str(phase.get("phase_id", ""))
        if not phase_id.endswith("_batch"):
            continue
        expected_region = phase_id[: -len("_batch")]
        for hostname in phase.get("devices", []) or []:
            row = by_name.get(hostname)
            if not row:
                continue
            actual = device_region(row, campus_regions)
            if actual and actual != expected_region:
                return False
    return True


def forward_path_authoritative(path: str) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/")
    if normalized.startswith("/app/output/") or "/output/rendered/" in normalized:
        return False
    if normalized.startswith("output/") or normalized.startswith("rendered/"):
        return False
    return True


def resolve_env_path(path: str) -> Path:
    if not path:
        return ENV / "__missing__"
    if path.startswith("/app/environment/"):
        return Path(path)
    if path.startswith("/"):
        return Path(path)
    return ENV / path


PRE_WAVE3_SNAPSHOT_MARKER = "! apexora-pre-wave3-boundary"


def _snapshot_body(rb_text: str) -> str:
    if rb_text.startswith(PRE_WAVE3_SNAPSHOT_MARKER):
        return rb_text.split("\n", 1)[-1] if "\n" in rb_text else ""
    return rb_text


def rollback_snapshot_is_pre_change(hostname: str, forward: str, rollback: str) -> bool:
    fwd_path = resolve_env_path(forward)
    rb_path = resolve_env_path(rollback)
    if not fwd_path.is_file() or not rb_path.is_file():
        return False
    rb_text = rb_path.read_text(encoding="utf-8")
    if not rb_text.startswith(PRE_WAVE3_SNAPSHOT_MARKER):
        return False
    fwd_text = fwd_path.read_text(encoding="utf-8")
    body = _snapshot_body(rb_text)
    if fwd_text != body:
        return True
    if hostname == CANARY_ANCHOR:
        return True
    return not any(marker in fwd_text for marker in LEGACY_ACL)


def rollback_authoritative() -> bool:
    if not wave_authoritative():
        return False
    bundles = load_yaml("deployment/rollback/bundles.yaml").get("bundles", {})
    scope = validation_scope_hostnames()
    if set(scope) - set(bundles.keys()):
        return False
    for hostname in scope:
        bundle = bundles.get(hostname, {})
        forward = bundle.get("forward", "")
        rollback = bundle.get("rollback", "")
        validation = bundle.get("validation_command", "")
        if not forward or not rollback:
            return False
        if not forward_path_authoritative(forward) or not forward_path_authoritative(rollback):
            return False
        if not resolve_env_path(forward).is_file() or not resolve_env_path(rollback).is_file():
            return False
        if not rollback_snapshot_is_pre_change(hostname, forward, rollback):
            return False
        if LEGACY_HOOK in validation:
            return False
        if not validation_command_matches(hostname, validation):
            return False
    return True


def config_authoritative_m3() -> bool:
    return config_authoritative_m2() and acl_authoritative() and wave_authoritative() and rollback_authoritative()


def evidence_export_invariants(doc: dict[str, Any]) -> list[str]:
    """Documented migration_evidence.json invariants (sealed schema + fleet contract)."""
    violations: list[str] = []
    if doc.get("schema_version") != "apexora-segmentation-evidence-1":
        violations.append("schema_version")
    if doc.get("device_count") != DEVICE_COUNT:
        violations.append("device_count")
    if doc.get("as_of") != evaluation_as_of():
        violations.append("as_of")
    devices = doc.get("devices") or []
    if len(devices) != DEVICE_COUNT:
        violations.append("devices_length")
    lineage = doc.get("lineage") or {}
    if lineage.get("stage") != "evidence":
        violations.append("lineage.stage")
    if list(lineage.get("spine") or []) != list(SPINE):
        violations.append("lineage.spine")
    return violations


def vlan_export_invariants(doc: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if doc.get("schema_version") != "apexora-vlan-conformance-1":
        violations.append("schema_version")
    if doc.get("vlan_catalog_count") != VLAN_CATALOG_COUNT:
        violations.append("vlan_catalog_count")
    devices = doc.get("devices") or []
    if len(devices) != IN_SCOPE_COUNT:
        violations.append("devices_length")
    lineage = doc.get("lineage") or {}
    if lineage.get("stage") != "vlan-check":
        violations.append("lineage.stage")
    return violations


def trunk_export_invariants(doc: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if doc.get("schema_version") != "apexora-trunk-conformance-1":
        violations.append("schema_version")
    if doc.get("trunk_link_count") != TRUNK_LINK_COUNT:
        violations.append("trunk_link_count")
    devices = doc.get("devices") or []
    if len(devices) != IN_SCOPE_COUNT:
        violations.append("devices_length")
    lineage = doc.get("lineage") or {}
    if lineage.get("stage") != "trunk-check":
        violations.append("lineage.stage")
    if lineage.get("depends_on") != ["vlan-check"]:
        violations.append("lineage.depends_on")
    return violations


def acl_export_invariants(doc: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if doc.get("schema_version") != "apexora-acl-conformance-1":
        violations.append("schema_version")
    if doc.get("policy_catalog_count") != POLICY_CATALOG_COUNT:
        violations.append("policy_catalog_count")
    devices = doc.get("devices") or []
    if len(devices) != VALIDATION_SCOPE_COUNT:
        violations.append("devices_length")
    hosts = {str(row.get("hostname")) for row in devices}
    if hosts != set(EXPECTED_VALIDATION_SCOPE):
        violations.append("validation_scope_hosts")
    lineage = doc.get("lineage") or {}
    if lineage.get("stage") != "acl-check":
        violations.append("lineage.stage")
    if lineage.get("depends_on") != ["vlan-check", "trunk-check"]:
        violations.append("lineage.depends_on")
    return violations


def wave_export_invariants(doc: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if doc.get("schema_version") != "apexora-wave-readiness-1":
        violations.append("schema_version")
    if doc.get("wave_id") != "wave_3":
        violations.append("wave_id")
    if doc.get("regional_order") != REGIONAL_ORDER:
        violations.append("regional_order")
    if doc.get("post_deploy_hook") != ACTIVE_HOOK:
        violations.append("post_deploy_hook")
    if doc.get("legacy_hooks_present") is not False:
        violations.append("legacy_hooks_present")
    if doc.get("missing_devices"):
        violations.append("missing_devices")
    phases = doc.get("phases") or []
    if not phases or phases[0].get("phase_id") != "canary":
        violations.append("canary_first")
    lineage = doc.get("lineage") or {}
    if lineage.get("stage") != "wave-plan":
        violations.append("lineage.stage")
    if lineage.get("depends_on") != ["render"]:
        violations.append("lineage.depends_on")
    return violations


def rollback_export_invariants(doc: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if doc.get("schema_version") != "apexora-rollback-manifest-1":
        violations.append("schema_version")
    if doc.get("device_count") != VALIDATION_SCOPE_COUNT:
        violations.append("device_count")
    if doc.get("missing_hosts"):
        violations.append("missing_hosts")
    bundles = doc.get("bundles") or []
    hosts = {str(row.get("hostname")) for row in bundles}
    if hosts != set(EXPECTED_VALIDATION_SCOPE):
        violations.append("validation_scope_hosts")
    lineage = doc.get("lineage") or {}
    if lineage.get("stage") != "rollback-audit":
        violations.append("lineage.stage")
    if lineage.get("depends_on") != ["wave-plan"]:
        violations.append("lineage.depends_on")
    for row in bundles:
        hostname = str(row.get("hostname", ""))
        if not validation_command_matches(hostname, str(row.get("validation_command", ""))):
            violations.append(f"validation_command:{hostname}")
        if row.get("forward_exists") is not True or row.get("rollback_exists") is not True:
            violations.append(f"bundle_exists:{hostname}")
    return violations


def all_vlan_pass(doc: dict[str, Any]) -> bool:
    return all(row["pass"] for row in doc["devices"])


def all_trunk_pass(doc: dict[str, Any]) -> bool:
    return all(row["pass"] for row in doc["devices"])


def all_acl_pass(doc: dict[str, Any]) -> bool:
    return all(row["pass"] for row in doc["devices"])


def sample_in_scope_access() -> str:
    for row in in_scope_devices():
        if row["role"] == "access":
            return row["hostname"]
    raise RuntimeError("no in-scope access switch")


def sample_gateway_binding() -> dict[str, Any]:
    bindings = gateway_bindings()
    if not bindings:
        raise RuntimeError("no gateway bindings")
    return bindings[0]
