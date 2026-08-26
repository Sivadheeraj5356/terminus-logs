#!/usr/bin/env python3
"""SegmentFirst deployment pipeline — transitive stage spine.

Stage order (binding): vlan-check → trunk-check → acl-check → render →
wave-plan → rollback-audit → evidence.

Each stage derives from upstream resolution and prior stage artifacts as
documented in docs/OPERATIONS.md.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import netseg_resolve as R

PRE_WAVE3_SNAPSHOT_MARKER = "! apexora-pre-wave3-boundary"
LEGACY_ACL_MARKERS = set(R.LEGACY_ACL)


def env_root() -> Path:
    return Path(os.environ.get("ENV_ROOT", "/app/environment"))


def output_root() -> Path:
    return Path(os.environ.get("OUTPUT_ROOT", "/app/output"))


def resolve_env_path(env: Path, path: str) -> Path:
    if not path:
        return env / "__missing__"
    if path.startswith("/app/environment/"):
        return Path(path)
    if path.startswith("/"):
        return Path(path)
    return env / path


def forward_path_authoritative(path: str) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/")
    if normalized.startswith("/app/output/") or "/output/rendered/" in normalized:
        return False
    if normalized.startswith("output/") or normalized.startswith("rendered/"):
        return False
    return True


def _snapshot_body(rb_text: str) -> str:
    if rb_text.startswith(PRE_WAVE3_SNAPSHOT_MARKER):
        return rb_text.split("\n", 1)[-1] if "\n" in rb_text else ""
    return rb_text


def rollback_snapshot_is_pre_change(env: Path, forward: str, rollback: str, hostname: str) -> bool:
    fwd_path = resolve_env_path(env, forward)
    rb_path = resolve_env_path(env, rollback)
    if not fwd_path.is_file() or not rb_path.is_file():
        return False
    rb_text = rb_path.read_text(encoding="utf-8")
    if not rb_text.startswith(PRE_WAVE3_SNAPSHOT_MARKER):
        return False
    fwd_text = fwd_path.read_text(encoding="utf-8")
    body = _snapshot_body(rb_text)
    if fwd_text != body:
        return True
    if hostname == R.CANARY_ANCHOR:
        return True
    return not any(marker in fwd_text for marker in LEGACY_ACL_MARKERS)


def legacy_vlan_on_access(text: str) -> bool:
    for m in re.finditer(r"switchport access vlan (\d+)", text):
        vid = int(m.group(1))
        if 101 <= vid <= 180:
            return True
    return False


def assembly_active_sections(env: Path) -> list[str]:
    precedence = R.load_yaml(env / "configs/assembly/source_precedence.yaml")
    return sorted(str(s) for s in precedence.get("active_sections", []))


def validation_scope_rows(env: Path) -> list[dict[str, Any]]:
    names = set(R.validation_scope_hostnames(env))
    by_name = {d["hostname"]: d for d in R.devices(env)}
    return [by_name[h] for h in sorted(names) if h in by_name]


def _pass_map(doc: dict[str, Any] | None) -> dict[str, bool]:
    if not doc:
        return {}
    return {str(row["hostname"]): bool(row.get("pass")) for row in doc.get("devices", [])}


def stage_vlan_check() -> None:
    env = env_root()
    out = output_root() / "vlan_conformance.json"
    resolved = R.resolve_canonical_vlans(env)
    allowed = resolved["canonical_ids"]
    rows = []
    for row in R.devices(env):
        if not R.in_scope(row):
            continue
        hostname = row["hostname"]
        if row["role"] != "access":
            rows.append({"hostname": hostname, "pass": True, "violations": []})
            continue
        conf = R.read_conf(R.device_running_conf(env, hostname, "access"))
        violations: list[str] = []
        if resolved["source_drift"]:
            violations.append("vlan_source_drift")
        for m in re.finditer(r"switchport access vlan (\d+)", conf):
            vid = int(m.group(1))
            if vid not in allowed:
                violations.append(f"vlan_{vid}_not_in_catalog")
            if 101 <= vid <= 180:
                violations.append(f"legacy_vlan_{vid}")
        meta_path = env / "switches/access" / hostname / "vlan.local.yaml"
        if meta_path.is_file() and R.load_yaml(meta_path).get("duplicate_vlan_conflict"):
            violations.append("duplicate_vlan_assignment")
        rows.append({"hostname": hostname, "pass": len(violations) == 0, "violations": violations})

    R.dump_json(
        out,
        {
            "schema_version": "apexora-vlan-conformance-1",
            "vlan_catalog_count": resolved["vlan_catalog_count"],
            "devices": rows,
            "lineage": {
                "stage": "vlan-check",
                "resolved_from": resolved["resolved_from"],
                "source_drift": resolved["source_drift"],
            },
        },
    )


def stage_trunk_check() -> None:
    env = env_root()
    out_root = output_root()
    out = out_root / "trunk_conformance.json"
    vlan_doc = R.load_stage_output(out_root, "vlan_conformance.json")
    vlan_pass = _pass_map(vlan_doc)
    # Trunk depends on resolved VLANs: access hosts that failed VLAN cannot pass trunk.
    policy_mode = R.trunk_policy_mode(env)
    seed_rows = R.load_yaml(env / "trunks/violations_seed.yaml").get("violations") or []
    seed_by_host: dict[str, list[str]] = {}
    for entry in seed_rows:
        device = str(entry.get("device", ""))
        issue = str(entry.get("issue", ""))
        if device and issue:
            seed_by_host.setdefault(device, []).append(issue)

    rows = []
    for row in R.devices(env):
        if not R.in_scope(row):
            continue
        hostname = row["hostname"]
        conf = R.read_conf(R.device_running_conf(env, hostname, row["role"]))
        violations = R.trunk_live_violations(conf, row["role"], policy_mode=policy_mode)
        for issue in seed_by_host.get(hostname, []):
            if issue not in violations:
                violations.append(issue)
        if row["role"] == "access" and vlan_pass and not vlan_pass.get(hostname, False):
            if "upstream_vlan_failed" not in violations:
                violations.append("upstream_vlan_failed")
        rows.append({"hostname": hostname, "pass": len(violations) == 0, "violations": violations})

    R.dump_json(
        out,
        {
            "schema_version": "apexora-trunk-conformance-1",
            "trunk_link_count": R.trunk_link_count(env),
            "devices": rows,
            "lineage": {
                "stage": "trunk-check",
                "depends_on": ["vlan-check"],
                "trunk_policy": "interfaces/trunk/trunk_policy.yaml",
                "vlan_artifact_present": vlan_doc is not None,
            },
        },
    )


def stage_acl_check() -> None:
    env = env_root()
    out_root = output_root()
    out = out_root / "acl_conformance.json"
    trunk_doc = R.load_stage_output(out_root, "trunk_conformance.json")
    trunk_pass = _pass_map(trunk_doc)
    vrf_res = R.resolve_vrfs(env)
    acl_res = R.resolve_acls_from_vrfs(env, vrf_res)
    campus_regions = R.campus_region_map(env)
    active = set(acl_res["active_names"])

    rows = []
    for row in validation_scope_rows(env):
        hostname = row["hostname"]
        region = R.device_region(env, row, campus_regions)
        allowed = set(acl_res["by_region"].get(region, []))
        conf = R.read_conf(R.device_running_conf(env, hostname, row["role"]))
        refs = R.acl_refs(conf)
        violations = sorted(
            r for r in refs if r in R.LEGACY_ACL or (r.startswith("OG-FLAT-") and r not in active)
        )
        violations.extend(sorted(r for r in refs if r.startswith("SEG-") and r not in active))
        # Transitive: SEG refs must also be allowed by regionally resolved VRFs.
        violations.extend(
            sorted(
                r
                for r in refs
                if r.startswith("SEG-") and r in active and r not in allowed
            )
        )
        # WAN edges must not retain the legacy VRF; CORP-IT must be regionally resolved.
        if row["role"] == "wan_edge":
            if R.LEGACY_VRF in conf:
                violations.append("legacy_vrf_present")
            if R.CANONICAL_WAN_VRF not in vrf_res["by_region"].get(region, []):
                violations.append("canonical_vrf_not_in_region")
        # In-scope hosts that failed trunk cannot pass ACL (interface policy gate).
        if R.in_scope(row) and trunk_pass and not trunk_pass.get(hostname, False):
            if "upstream_trunk_failed" not in violations:
                violations.append("upstream_trunk_failed")
        rows.append({"hostname": hostname, "pass": len(violations) == 0, "violations": violations})

    R.dump_json(
        out,
        {
            "schema_version": "apexora-acl-conformance-1",
            "policy_catalog_count": acl_res["policy_catalog_count"],
            "devices": rows,
            "lineage": {
                "stage": "acl-check",
                "depends_on": ["vlan-check", "trunk-check"],
                "resolved_vrfs_by_region": {k: len(v) for k, v in vrf_res["by_region"].items()},
                "allowed_acl_count_by_region": {k: len(v) for k, v in acl_res["by_region"].items()},
                "resolved_from": acl_res["resolved_from"],
                "trunk_artifact_present": trunk_doc is not None,
            },
        },
    )


def stage_render() -> None:
    env = env_root()
    out_root = output_root()
    dest = out_root / "rendered"
    dest.mkdir(parents=True, exist_ok=True)
    # Clear previous renders so omitted hosts do not linger.
    for stale in dest.glob("*.conf"):
        stale.unlink()

    vlan_pass = _pass_map(R.load_stage_output(out_root, "vlan_conformance.json"))
    trunk_pass = _pass_map(R.load_stage_output(out_root, "trunk_conformance.json"))
    acl_pass = _pass_map(R.load_stage_output(out_root, "acl_conformance.json"))
    validation = set(R.validation_scope_hostnames(env))
    policy_mode = R.trunk_policy_mode(env)

    rendered = []
    for row in R.devices(env):
        if not R.in_scope(row):
            continue
        hostname = row["hostname"]
        if row["role"] == "access" and vlan_pass and not vlan_pass.get(hostname, False):
            continue
        if trunk_pass and not trunk_pass.get(hostname, False):
            continue
        if hostname in validation and acl_pass and not acl_pass.get(hostname, False):
            continue
        src = R.device_running_conf(env, hostname, row["role"])
        if src is None:
            continue
        text = src.read_text(encoding="utf-8")
        # Interface policy gate: selective trunks only.
        if policy_mode == "selective" and re.search(r"switchport trunk allowed vlan all\b", text):
            continue
        (dest / f"{hostname}.conf").write_text(text, encoding="utf-8")
        rendered.append(hostname)

    # Render has no JSON export contract; lineage is recorded by wave-plan/evidence
    # via the rendered/ host set (docs/OPERATIONS.md dependency spine).
    _ = rendered


def stage_wave_plan() -> None:
    env = env_root()
    out_root = output_root()
    out = out_root / "wave_readiness.json"
    wave = R.load_yaml(env / "deployment/waves/wave_3.yaml")
    canary = R.load_yaml(env / "deployment/canary/groups.yaml")
    hook = canary.get("groups", [{}])[0].get("gate", {}).get("validation_hook", "")
    legacy_present = (
        R.LEGACY_HOOK in hook
        or bool(wave.get("legacy_hooks_present"))
        or (env / R.LEGACY_HOOK).is_file()
    )
    phases = wave.get("phases", [])
    phased_devices: set[str] = set()
    for phase in phases:
        phased_devices.update(phase.get("devices", []))

    scope = set(R.validation_scope_hostnames(env))
    rendered = R.rendered_hostnames(out_root)
    in_scope_names = {d["hostname"] for d in R.devices(env) if R.in_scope(d)}
    # Waves derive from rendered bundles: in-scope validation hosts must be rendered.
    unrendered = sorted((scope & in_scope_names) - rendered)
    missing = sorted((scope - phased_devices) | set(unrendered))

    # Regional batch membership must respect campus_index regions for phased hosts.
    campus_regions = R.campus_region_map(env)
    by_name = {d["hostname"]: d for d in R.devices(env)}
    region_drift: list[str] = []
    for phase in phases:
        phase_id = str(phase.get("phase_id", ""))
        if not phase_id.endswith("_batch"):
            continue
        expected_region = phase_id[: -len("_batch")]
        for hostname in phase.get("devices", []) or []:
            row = by_name.get(hostname)
            if not row:
                continue
            actual = R.device_region(env, row, campus_regions)
            if actual and actual != expected_region:
                region_drift.append(hostname)

    R.dump_json(
        out,
        {
            "schema_version": "apexora-wave-readiness-1",
            "wave_id": wave.get("wave_id", "wave_3"),
            "canary_first": bool(wave.get("canary_first")) and phases and phases[0].get("phase_id") == "canary",
            "regional_order": wave.get("regional_order", []),
            "legacy_hooks_present": legacy_present,
            "phases": phases,
            "missing_devices": missing,
            "post_deploy_hook": wave.get("post_deploy_hook"),
            "lineage": {
                "stage": "wave-plan",
                "depends_on": ["render"],
                "rendered_count": len(rendered),
                "unrendered_in_scope_validation": unrendered,
                "regional_membership_drift": sorted(set(region_drift)),
            },
        },
    )


def stage_rollback_audit() -> None:
    env = env_root()
    out_root = output_root()
    out = out_root / "rollback_bundle_manifest.json"
    wave_doc = R.load_stage_output(out_root, "wave_readiness.json")
    bundles = R.load_yaml(env / "deployment/rollback/bundles.yaml").get("bundles", {})

    # Rollback host set is derived from deployment-wave phase membership when present,
    # intersected with the immutable validation scope.
    scope_names = R.validation_scope_hostnames(env)
    if wave_doc:
        phased: set[str] = set()
        for phase in wave_doc.get("phases", []) or []:
            phased.update(phase.get("devices", []) or [])
        # Prefer wave-derived coverage; fall back to full scope for row emission.
        required = [h for h in scope_names if h in phased] or list(scope_names)
        # Hosts in scope but missing from ready waves are reported missing.
        wave_gaps = set(wave_doc.get("missing_devices") or [])
    else:
        required = list(scope_names)
        wave_gaps = set(scope_names)
        phased = set()

    by_name = {d["hostname"]: d for d in R.devices(env)}
    rows = []
    missing_hosts = []
    for hostname in required:
        if hostname not in by_name:
            missing_hosts.append(hostname)
            continue
        bundle = bundles.get(hostname, {})
        forward = bundle.get("forward", "")
        rollback = bundle.get("rollback", "")
        validation = bundle.get("validation_command", "")
        fwd_ok = (
            forward_path_authoritative(forward)
            and resolve_env_path(env, forward).is_file()
            if forward
            else False
        )
        rb_ok = (
            forward_path_authoritative(rollback)
            and resolve_env_path(env, rollback).is_file()
            and rollback_snapshot_is_pre_change(env, forward, rollback, hostname)
            if rollback and forward
            else False
        )
        if not bundle or hostname in wave_gaps:
            if hostname not in missing_hosts:
                missing_hosts.append(hostname)
        rows.append(
            {
                "hostname": hostname,
                "forward": forward,
                "rollback": rollback,
                "validation_command": validation,
                "forward_exists": fwd_ok,
                "rollback_exists": rb_ok,
            }
        )

    # Also flag validation-scope hosts omitted from wave-derived required set.
    for hostname in scope_names:
        if hostname not in {r["hostname"] for r in rows}:
            missing_hosts.append(hostname)

    R.dump_json(
        out,
        {
            "schema_version": "apexora-rollback-manifest-1",
            "device_count": len(scope_names),
            "indexed_count": len(bundles),
            "missing_hosts": sorted(set(missing_hosts)),
            "bundles": rows,
            "lineage": {
                "stage": "rollback-audit",
                "depends_on": ["wave-plan"],
                "wave_artifact_present": wave_doc is not None,
                "wave_derived_host_count": len(required),
                "phased_host_count": len(phased) if wave_doc else 0,
            },
        },
    )


def stage_evidence() -> None:
    """Final fan-in: evidence observes live config and all upstream stage artifacts."""
    env = env_root()
    out_root = output_root()
    out = out_root / "migration_evidence.json"
    precedence = R.load_yaml(env / "configs/assembly/source_precedence.yaml")
    consult_legacy = bool(precedence.get("consult_legacy_when_present", False))
    clock = json.loads((env / "data/evaluation_clock.json").read_text(encoding="utf-8"))
    retired = list(precedence.get("retired_vlan_families", []))
    active_ids = assembly_active_sections(env)
    m1_ids = sorted(
        {
            "policy-source-precedence-2026",
            "vlan-assignment-standards-2026",
            "vlan-identity",
            "vlan-naming-standard-2026",
            "vrf-policy-2026",
            "device-hostname-standard-2026",
        }
        & set(active_ids)
    )

    vlan_doc = R.load_stage_output(out_root, "vlan_conformance.json")
    trunk_doc = R.load_stage_output(out_root, "trunk_conformance.json")
    acl_doc = R.load_stage_output(out_root, "acl_conformance.json")
    wave_doc = R.load_stage_output(out_root, "wave_readiness.json")
    rollback_doc = R.load_stage_output(out_root, "rollback_bundle_manifest.json")
    rendered = R.rendered_hostnames(out_root)
    vlan_res = R.resolve_canonical_vlans(env)
    vrf_res = R.resolve_vrfs(env)
    acl_res = R.resolve_acls_from_vrfs(env, vrf_res)

    rows = []
    for row in R.devices(env):
        hostname = row["hostname"]
        role = row["role"]
        conf = R.read_conf(R.device_running_conf(env, hostname, role))
        legacy_vlan = legacy_vlan_on_access(conf) if role == "access" else False
        dup = False
        meta = env / "switches/access" / hostname / "vlan.local.yaml"
        if meta.is_file():
            dup = bool(R.load_yaml(meta).get("duplicate_vlan_conflict", False))
        consulted: list[str] = []
        if consult_legacy:
            consulted = sorted(set(active_ids + ["legacy/vlan_map_flat.csv"]))
        else:
            consulted = list(m1_ids)
        legacy_sources = []
        if consult_legacy or R.LEGACY_HOOK in conf or "legacy/" in conf:
            legacy_sources.append("legacy/vlan_map_flat.csv")
        rows.append(
            {
                "hostname": hostname,
                "role": role,
                "campus_id": row.get("campus_id"),
                "migration_state": row.get("migration_state"),
                "legacy_vlan_ids_present": legacy_vlan,
                "duplicate_vlans": [hostname] if dup else [],
                "legacy_sources_consulted": legacy_sources,
                "source_sections_consulted": consulted,
                "retired_vlan_families": list(retired),
                "superseded_sections": []
                if not consult_legacy
                else list(precedence.get("superseded_sections", [])),
            }
        )

    R.dump_json(
        out,
        {
            "schema_version": "apexora-segmentation-evidence-1",
            "as_of": clock["as_of"],
            "device_count": len(rows),
            "devices": rows,
            "lineage": {
                "stage": "evidence",
                "spine": list(R.SPINE),
                "depends_on": [
                    "vlan-check",
                    "trunk-check",
                    "acl-check",
                    "render",
                    "wave-plan",
                    "rollback-audit",
                ],
                "vlan_catalog_count": vlan_res["vlan_catalog_count"],
                "vlan_source_drift": vlan_res["source_drift"],
                "resolved_vrf_count_by_region": {
                    k: len(v) for k, v in vrf_res["by_region"].items()
                },
                "acl_policy_catalog_count": acl_res["policy_catalog_count"],
                "rendered_bundle_count": len(rendered),
                "upstream_artifacts_present": {
                    "vlan_conformance": vlan_doc is not None,
                    "trunk_conformance": trunk_doc is not None,
                    "acl_conformance": acl_doc is not None,
                    "rendered": bool(rendered),
                    "wave_readiness": wave_doc is not None,
                    "rollback_manifest": rollback_doc is not None,
                },
                "wave_missing_count": len((wave_doc or {}).get("missing_devices") or []),
                "rollback_missing_count": len((rollback_doc or {}).get("missing_hosts") or []),
            },
        },
    )


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    stages = {
        "vlan-check": stage_vlan_check,
        "trunk-check": stage_trunk_check,
        "acl-check": stage_acl_check,
        "render": stage_render,
        "wave-plan": stage_wave_plan,
        "rollback-audit": stage_rollback_audit,
        "evidence": stage_evidence,
    }
    if stage == "all":
        for name in R.SPINE:
            stages[name]()
        return
    if stage not in stages:
        raise SystemExit(f"unknown stage: {stage}")
    stages[stage]()


if __name__ == "__main__":
    main()
