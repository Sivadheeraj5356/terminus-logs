#!/usr/bin/env python3
"""Reconcile SegmentFirst Wave 3 configuration from authoritative catalogs.

Edits infrastructure configuration under ENV only — never writes pipeline outputs.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

LEGACY_VRF = "VRF-CORP"
CANONICAL_VRF = "CORP-IT"
LEGACY_ACL_MAP = {
    "ACL-INSIDE-ANY": "SEG-CORP-IT-IN",
    "ACL-EDGE-LEGACY": "SEG-DMZ-IN",
    "OG-FLAT-USER": "SEG-GUEST-IN",
    "OG-FLAT-FINANCE": "SEG-FINANCE-IN",
    "OG-FLAT-SERVER": "SEG-CORP-IT-IN",
}
ACTIVE_HOOK = "services/hooks/post-validate.sh"
LEGACY_HOOK = "legacy/hooks/pre-validate-legacy.sh"
PRE_WAVE3_SNAPSHOT_MARKER = "! apexora-pre-wave3-boundary snapshot — do not overwrite after migration edits"
REGIONAL_ORDER = ["amer", "emea", "apac"]

def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dump_yaml(path: Path, data: Any) -> None:
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")


def dump_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def devices(env: Path) -> list[dict[str, Any]]:
    inv = load_yaml(env / "inventory/device_inventory.yaml")
    return sorted(inv.get("devices", []), key=lambda d: d["hostname"])


def in_scope(row: dict[str, Any]) -> bool:
    return row.get("migration_state") in {"legacy", "partial"}


def validation_scope_hostnames(env: Path) -> list[str]:
    scope = load_yaml(env / "inventory/wave3_validation_scope.yaml")
    return list(scope.get("hostnames", []))


def validation_scope(env: Path) -> list[dict[str, Any]]:
    names = set(validation_scope_hostnames(env))
    by_name = {d["hostname"]: d for d in devices(env)}
    return [by_name[h] for h in sorted(names) if h in by_name]


def campus_region(env: Path) -> dict[str, str]:
    doc = load_yaml(env / "inventory/campus_index.yaml")
    return {c["id"]: c["region"] for c in doc.get("campuses", [])}


def device_tree_paths(env: Path, hostname: str, role: str) -> list[Path]:
    paths: list[Path] = []
    if role == "access":
        base = env / "switches/access" / hostname
    elif role == "distribution":
        base = env / "switches/distribution" / hostname
    elif role == "core":
        base = env / "switches/core" / hostname
    elif role == "wan_edge":
        base = next((p for p in (env / "routers").rglob(hostname) if p.is_dir()), None)
        if base is None:
            return []
    else:
        return []
    if (base / "running.conf").is_file():
        paths.append(base / "running.conf")
    iface = base / "interfaces"
    if iface.is_dir():
        paths.extend(sorted(iface.glob("*.conf")))
    if role == "distribution" and (base / "svi.conf").is_file():
        paths.append(base / "svi.conf")
    if role == "wan_edge" and (base / "vrf.conf").is_file():
        paths.append(base / "vrf.conf")
    return paths


def replace_in_files(paths: list[Path], replacements: dict[str, str]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in replacements.items():
            text = text.replace(old, new)
        if text != original:
            dump_text(path, text)


def fix_source_precedence(env: Path) -> None:
    path = env / "configs/assembly/source_precedence.yaml"
    doc = load_yaml(path)
    doc["consult_legacy_when_present"] = False
    dump_yaml(path, doc)


def fix_access_vlan_identity(env: Path, hostname: str) -> None:
    base = env / "switches/access" / hostname
    meta_path = base / "vlan.local.yaml"
    if not meta_path.is_file():
        return
    meta = load_yaml(meta_path)
    canon = str(meta["canonical_vlan"])
    legacy = str(meta["legacy_vlan"])
    paths = device_tree_paths(env, hostname, "access")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            rf"switchport access vlan {legacy}\b",
            f"switchport access vlan {canon}",
            text,
        )
        text = re.sub(
            r"switchport trunk allowed vlan all\b",
            f"switchport trunk allowed vlan {canon},{int(canon)+1},{int(canon)+2}",
            text,
        )
        dump_text(path, text)
    meta["configured_vlan"] = int(canon)
    meta["duplicate_vlan_conflict"] = False
    dump_yaml(meta_path, meta)


def fix_router_vrf(env: Path, hostname: str) -> None:
    paths = device_tree_paths(env, hostname, "wan_edge")
    replace_in_files(
        paths,
        {
            f"ip vrf forwarding {LEGACY_VRF}": f"ip vrf forwarding {CANONICAL_VRF}",
            f"address-family ipv4 vrf {LEGACY_VRF}": f"address-family ipv4 vrf {CANONICAL_VRF}",
        },
    )


def clear_identity_audit_findings(env: Path) -> None:
    path = env / "inventory/audit_findings.yaml"
    doc = load_yaml(path)
    kept = []
    identity_codes = {"legacy_vlan_ids_present", "partial_vlan_mapping", "duplicate_vlan_assignment"}
    for item in doc.get("findings", []):
        codes = set(item.get("codes", []))
        if codes & identity_codes:
            continue
        kept.append(item)
    doc["findings"] = kept
    dump_yaml(path, doc)


def selective_trunk_allowlist(canon: int) -> str:
    return f"{canon},{canon + 1},{canon + 2}"


def remove_access_layer_gateway(text: str) -> str:
    text = re.sub(
        r"^interface Vlan\d+\n(?: .+\n)*?^\s+ip address .+\n(?: .+\n)*?(?=^!)",
        "",
        text,
        flags=re.M,
    )
    text = re.sub(r"^ip default-gateway .+\n", "", text, flags=re.M)
    return text


def fix_access_trunk_and_gateway(env: Path, hostname: str) -> None:
    base = env / "switches/access" / hostname
    meta_path = base / "vlan.local.yaml"
    canon = int(load_yaml(meta_path)["canonical_vlan"]) if meta_path.is_file() else 2101
    allow = selective_trunk_allowlist(canon)
    paths = device_tree_paths(env, hostname, "access")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"switchport trunk allowed vlan all\b", f"switchport trunk allowed vlan {allow}", text)
        text = re.sub(r"switchport trunk allowed vlan 3001-3099", "switchport trunk allowed vlan 2001-2180", text)
        if path.name == "running.conf":
            text = remove_access_layer_gateway(text)
        dump_text(path, text)


def fix_dist_core_trunks(env: Path, hostname: str, role: str) -> None:
    paths = device_tree_paths(env, hostname, role)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        text = text.replace("switchport trunk allowed vlan all", "switchport trunk allowed vlan 2001-2180")
        text = text.replace("2001-2099,3001-3099", "2001-2180")
        dump_text(path, text)


def clear_trunk_audit_findings(env: Path) -> None:
    path = env / "inventory/audit_findings.yaml"
    doc = load_yaml(path)
    trunk_codes = {"trunk_all_vlans", "access_layer_svi", "access_layer_gateway", "over_permissive_allowed_vlan"}
    kept = []
    for item in doc.get("findings", []):
        if set(item.get("codes", [])) & trunk_codes:
            continue
        kept.append(item)
    doc["findings"] = kept
    dump_yaml(path, doc)

    seed = env / "trunks/violations_seed.yaml"
    if seed.is_file():
        doc = load_yaml(seed)
        doc["violations"] = []
        dump_yaml(seed, doc)


def ensure_vrf_definition(text: str, vrf: str, rd: str) -> str:
    if f"ip vrf {vrf}" in text:
        return text
    block = (
        f"ip vrf {vrf}\n"
        f" rd {rd}\n"
        f" route-target export {rd}\n"
        f" route-target import {rd}\n"
        "!\n"
    )
    return text.replace("ip routing\n", f"ip routing\n!\n{block}", 1)


def ensure_gateway_svi(text: str, vlan_id: int, vrf: str, vip: str, acl: str) -> str:
    svi = (
        f"interface Vlan{vlan_id}\n"
        f" description {vrf} gateway SVI\n"
        f" ip vrf forwarding {vrf}\n"
        f" ip address {vip} 255.255.255.0\n"
        f" standby 10 ip {vip}\n"
        f" standby 10 priority 110\n"
        f" ip access-group {acl} in\n"
        "!\n"
    )
    if f"interface Vlan{vlan_id}" in text and vip in text:
        return text
    if f"interface Vlan{vlan_id}" in text:
        return re.sub(
            rf"interface Vlan{vlan_id}\n.*?(?=\ninterface |\nrouter |\Z)",
            svi.rstrip() + "\n",
            text,
            count=1,
            flags=re.S,
        )
    anchor = "interface TenGigabitEthernet"
    if anchor in text:
        return text.replace(anchor, svi + anchor, 1)
    return text.rstrip() + "\n" + svi


def fix_gateway_bindings(env: Path) -> None:
    vrf_cat = load_yaml(env / "vrfs/catalog.yaml").get("vrfs", {})
    bindings = load_yaml(env / "interfaces/gateway/gateway_bindings.yaml").get("bindings", [])
    for bind in bindings:
        primary = bind["primary"]
        vlan_id = int(bind["vlan_id"])
        vrf = bind["vrf"]
        vip = bind["vip"]
        meta = vrf_cat.get(vrf, {})
        rd = str(meta.get("rd", "65000:1000"))
        acl = meta.get("default_acl_profile", "SEG-CORP-IT-IN")
        base = env / "switches/distribution" / primary
        running = base / "running.conf"
        if not running.is_file():
            continue
        text = running.read_text(encoding="utf-8")
        text = ensure_vrf_definition(text, vrf, rd)
        text = ensure_gateway_svi(text, vlan_id, vrf, vip, acl)
        dump_text(running, text)
        iface_block = (
            f"interface Vlan{vlan_id}\n"
            f" ip vrf forwarding {vrf}\n"
            f" ip address {vip} 255.255.255.0\n"
            f" standby 10 ip {vip}\n"
        )
        svi_path = base / "svi.conf"
        if svi_path.is_file():
            svi_text = svi_path.read_text(encoding="utf-8")
            if f"interface Vlan{vlan_id}" in svi_text:
                svi_text = re.sub(
                    rf"interface Vlan{vlan_id}\n.*?(?=\ninterface |\Z)",
                    iface_block.rstrip() + "\n",
                    svi_text,
                    count=1,
                    flags=re.S,
                )
            else:
                svi_text = svi_text.rstrip() + "\n" + iface_block
            dump_text(svi_path, svi_text)
        else:
            dump_text(svi_path, iface_block)
        iface_path = base / "interfaces" / f"Vlan{vlan_id}.conf"
        iface_path.parent.mkdir(parents=True, exist_ok=True)
        dump_text(iface_path, iface_block)


def acl_binding_map(env: Path) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    dist = load_yaml(env / "acl/device_bindings/distribution_acl_map.yaml").get("bindings", {})
    for host, svcs in dist.items():
        for svi, acl in svcs.items():
            mapping[(host, svi)] = acl if acl not in LEGACY_ACL_MAP else LEGACY_ACL_MAP[acl]
    edge = load_yaml(env / "acl/device_bindings/router_edge_acl_map.yaml").get("bindings", {})
    for host, ifaces in edge.items():
        for iface, acl in ifaces.items():
            mapping[(host, iface)] = acl if acl not in LEGACY_ACL_MAP else LEGACY_ACL_MAP[acl]
    return mapping


def fix_device_acls(env: Path, hostname: str, role: str) -> None:
    bindings = acl_binding_map(env)
    paths = device_tree_paths(env, hostname, role)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for (host, _key), acl in bindings.items():
            if host == hostname:
                for legacy, active in LEGACY_ACL_MAP.items():
                    text = text.replace(f"ip access-group {legacy}", f"ip access-group {active}")
        for legacy, active in LEGACY_ACL_MAP.items():
            text = text.replace(f"ip access-group {legacy}", f"ip access-group {active}")
        dump_text(path, text)


def device_config_relpath(env: Path, hostname: str, role: str) -> str:
    if role == "access":
        return f"switches/access/{hostname}/running.conf"
    if role == "distribution":
        return f"switches/distribution/{hostname}/running.conf"
    if role == "core":
        return f"switches/core/{hostname}/running.conf"
    base = next((p for p in (env / "routers").rglob(hostname) if p.is_dir()), None)
    if base is None:
        return f"switches/access/{hostname}/running.conf"
    return str(base.relative_to(env)) + "/running.conf"


def capture_pre_change_snapshots(env: Path) -> None:
    """Capture rollback snapshots before migration edits; never overwrite existing."""
    snap_dir = env / "backups/pre_wave3"
    snap_dir.mkdir(parents=True, exist_ok=True)
    for row in validation_scope(env):
        hostname = row["hostname"]
        snap = snap_dir / f"{hostname}.conf.snapshot"
        if snap.is_file():
            continue
        rel = device_config_relpath(env, hostname, row["role"])
        src = env / rel
        if src.is_file():
            body = src.read_text(encoding="utf-8")
            snap.write_text(f"{PRE_WAVE3_SNAPSHOT_MARKER}\n{body}", encoding="utf-8")


def disable_legacy_hook(env: Path) -> None:
    hook_path = env / LEGACY_HOOK
    if hook_path.is_file():
        hook_path.unlink()


def fix_deployment_manifests(env: Path) -> None:
    hook = ACTIVE_HOOK
    canary_path = env / "deployment/canary/groups.yaml"
    canary = load_yaml(canary_path)
    for group in canary.get("groups", []):
        group.setdefault("gate", {})["validation_hook"] = hook
    dump_yaml(canary_path, canary)

    wave_path = env / "deployment/waves/wave_3.yaml"
    wave = load_yaml(wave_path)
    wave["post_deploy_hook"] = hook
    wave["legacy_hooks_present"] = False
    wave["regional_order"] = list(REGIONAL_ORDER)

    regions = campus_region(env)
    scope = validation_scope(env)
    canary_hosts = sorted(
        canary.get("groups", [{}])[0].get(
            "required_devices", ["acc-hq-dal-bldg1-01", "dist-hq-dal-main-01"]
        )
    )
    by_region: dict[str, list[str]] = {r: [] for r in REGIONAL_ORDER}
    for row in scope:
        host = row["hostname"]
        if host in canary_hosts:
            continue
        region = regions.get(row.get("campus_id", ""), "amer")
        by_region.setdefault(region, []).append(host)

    phases: list[dict[str, Any]] = [
        {"phase_id": "canary", "campuses": ["campus-hq-dal"], "devices": canary_hosts},
    ]
    for region in REGIONAL_ORDER:
        hosts = sorted(by_region.get(region, []))
        if not hosts:
            continue
        phases.append({"phase_id": f"{region}_batch", "region": region, "devices": hosts})
    wave["phases"] = phases
    dump_yaml(wave_path, wave)

    hook_reg = env / "deployment/hooks/post_validate.conf"
    dump_text(
        hook_reg,
        f"active_hook: {hook}\ndeprecated_hooks: []\n",
    )


def fix_rollback_bundles(env: Path) -> None:
    """Index rollback bundles; snapshot contents are captured pre-change only."""
    bundles: dict[str, Any] = {}
    targets = validation_scope(env)
    for row in targets:
        hostname = row["hostname"]
        rel = device_config_relpath(env, hostname, row["role"])
        snap = f"backups/pre_wave3/{hostname}.conf.snapshot"
        bundles[hostname] = {
            "forward": rel,
            "rollback": snap,
            "validation_command": f"{ACTIVE_HOOK} {hostname}",
        }
    dump_yaml(env / "deployment/rollback/bundles.yaml", {"schema_version": "apexora-rollback-1", "bundles": bundles})


def fix_m1(env: Path) -> None:
    fix_source_precedence(env)
    for row in devices(env):
        if row["role"] == "access" and in_scope(row):
            fix_access_vlan_identity(env, row["hostname"])
        if row["role"] == "wan_edge" and in_scope(row):
            fix_router_vrf(env, row["hostname"])
    clear_identity_audit_findings(env)


def fix_m2(env: Path) -> None:
    for row in devices(env):
        if not in_scope(row):
            continue
        if row["role"] == "access":
            fix_access_trunk_and_gateway(env, row["hostname"])
        elif row["role"] in {"distribution", "core"}:
            fix_dist_core_trunks(env, row["hostname"], row["role"])
    fix_gateway_bindings(env)
    clear_trunk_audit_findings(env)


def fix_m3(env: Path) -> None:
    capture_pre_change_snapshots(env)
    for row in validation_scope(env):
        fix_device_acls(env, row["hostname"], row["role"])
    fix_deployment_manifests(env)
    disable_legacy_hook(env)
    fix_rollback_bundles(env)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="/app/environment")
    parser.add_argument("stage", choices=["m1", "m2", "m3"])
    args = parser.parse_args()
    env = Path(args.env)
    if args.stage == "m1":
        fix_m1(env)
    elif args.stage == "m2":
        fix_m2(env)
    else:
        fix_m3(env)


if __name__ == "__main__":
    main()
