"""SegmentFirst Wave 3 verifier — identity, trunk/gateway, ACL/wave/rollback."""
from __future__ import annotations

import re

import pytest
import yaml

from helpers import (
    DEVICE_COUNT,
    ENV,
    EXPECTED_MIGRATION_STATE,
    EXPECTED_VALIDATION_SCOPE,
    EXPECTED_VLAN_IDS,
    OUTPUT,
    POLICY_CATALOG_COUNT,
    TRUNK_LINK_COUNT,
    VLAN_CATALOG_COUNT,
    assert_stage_ok,
    canonical_evidence,
    load_output,
    run_stage,
    run_stage_sequence,
    write_config,
)
import refmodel


FULL_SPINE = (
    "vlan-check",
    "trunk-check",
    "acl-check",
    "render",
    "wave-plan",
    "rollback-audit",
    "evidence",
)


@pytest.fixture(scope="module")
def spine_outputs() -> None:
    """Run the full transitive spine once per module; later fixtures only load exports."""
    result = run_stage_sequence(*FULL_SPINE)
    assert_stage_ok(result, "evidence")


@pytest.fixture(scope="module")
def evidence(spine_outputs: None) -> dict:
    return load_output("migration_evidence.json")


@pytest.fixture(scope="module")
def vlan_doc(spine_outputs: None) -> dict:
    return load_output("vlan_conformance.json")


@pytest.fixture(scope="module")
def trunk_doc(spine_outputs: None) -> dict:
    return load_output("trunk_conformance.json")


@pytest.fixture(scope="module")
def rendered_dir(spine_outputs: None) -> list:
    return sorted((OUTPUT / "rendered").glob("*.conf"))


@pytest.fixture(scope="module")
def acl_doc(spine_outputs: None) -> dict:
    return load_output("acl_conformance.json")


@pytest.fixture(scope="module")
def wave_doc(spine_outputs: None) -> dict:
    return load_output("wave_readiness.json")


@pytest.fixture(scope="module")
def rollback_doc(spine_outputs: None) -> dict:
    return load_output("rollback_bundle_manifest.json")


def _run_no_reset(*stages: str):
    """Re-run stages without clearing prior spine artifacts (anti-cheat isolation)."""
    last = None
    for stage in stages:
        last = run_stage(stage, reset=False)
        if last.returncode != 0:
            return last
    assert last is not None
    return last


class TestWave3ScopeContract:
    """Verifier-owned scope contracts — independent of agent-editable catalogs."""

    def test_exact_migration_state_map(self) -> None:
        """Inventory migration_state map must match the verifier golden map."""
        got = refmodel.inventory_migration_state_map()
        assert got == EXPECTED_MIGRATION_STATE
        assert len(got) == DEVICE_COUNT
        assert sum(1 for s in got.values() if s in {"legacy", "partial"}) == refmodel.IN_SCOPE_COUNT

    def test_exact_validation_scope(self) -> None:
        """Validation scope must match the verifier-owned 48-host golden list."""
        assert refmodel.validation_scope_hostnames() == EXPECTED_VALIDATION_SCOPE
        assert len(EXPECTED_VALIDATION_SCOPE) == refmodel.VALIDATION_SCOPE_COUNT
        assert refmodel.CANARY_ANCHOR in EXPECTED_VALIDATION_SCOPE
        assert refmodel.inventory_validation_scope_hosts() == EXPECTED_VALIDATION_SCOPE
        assert set(EXPECTED_VLAN_IDS) == set(range(2001, 2181))
        assert len(EXPECTED_VLAN_IDS) == VLAN_CATALOG_COUNT


class TestWave3Identity:
    """Validate VLAN migration, VRF bindings, and migration evidence exports."""

    @pytest.fixture(autouse=True)
    def _require_authoritative_config(self) -> None:
        assert refmodel.config_authoritative_m1(), "configuration not yet authoritative"

    def test_schema_and_device_count(self, evidence: dict) -> None:
        """Evidence export must match contract schema version, as_of, and fleet size."""
        assert refmodel.evidence_export_invariants(evidence) == []
        assert evidence["schema_version"] == "apexora-segmentation-evidence-1"
        assert evidence["device_count"] == DEVICE_COUNT
        assert evidence["as_of"] == refmodel.evaluation_as_of()

    def test_evidence_export_invariants(self, evidence: dict) -> None:
        """Evidence export must satisfy sealed schema and lineage invariants."""
        assert refmodel.evidence_export_invariants(evidence) == []
        lineage = evidence["lineage"]
        assert lineage["stage"] == "evidence"
        assert list(lineage["spine"]) == list(refmodel.SPINE)
        upstream = lineage.get("upstream_artifacts_present") or {}
        assert all(upstream.values())
        assert lineage.get("wave_missing_count") == 0
        assert lineage.get("rollback_missing_count") == 0

    def test_vlan_export_invariants(self, vlan_doc: dict) -> None:
        """VLAN conformance export must satisfy sealed schema and scope invariants."""
        assert refmodel.vlan_export_invariants(vlan_doc) == []

    def test_all_vlan_checks_pass(self, vlan_doc: dict) -> None:
        """Every in-scope access device must pass VLAN conformance."""
        assert refmodel.all_vlan_pass(vlan_doc)

    def test_vlan_catalog_count(self, vlan_doc: dict) -> None:
        """VLAN export must report the contract catalog size."""
        assert vlan_doc["vlan_catalog_count"] == VLAN_CATALOG_COUNT

    def test_no_legacy_sources_consulted(self, evidence: dict) -> None:
        """No device may consult the deprecated legacy VLAN map."""
        for row in evidence["devices"]:
            assert row["legacy_sources_consulted"] == []

    def test_retired_vlan_families_from_precedence(self, evidence: dict) -> None:
        """Evidence rows must carry retired VLAN families from assembly precedence."""
        expected = refmodel.retired_vlan_families()
        for row in evidence["devices"]:
            assert sorted(row["retired_vlan_families"]) == expected

    def test_superseded_sections_empty(self, evidence: dict) -> None:
        """Authoritative assembly must leave superseded sections empty."""
        for row in evidence["devices"]:
            assert row["superseded_sections"] == []
    def test_in_scope_access_no_legacy_vlans(self, evidence: dict) -> None:
        """In-scope access switches must not retain legacy VLAN IDs 101-180."""
        by_host = {row["hostname"]: row for row in evidence["devices"]}
        for row in refmodel.in_scope_devices():
            if row["role"] != "access":
                continue
            assert by_host[row["hostname"]]["legacy_vlan_ids_present"] is False

    def test_in_scope_no_duplicate_vlans(self, evidence: dict) -> None:
        """In-scope devices must not report duplicate VLAN assignment conflicts."""
        by_host = {row["hostname"]: row for row in evidence["devices"]}
        for row in refmodel.in_scope_devices():
            assert by_host[row["hostname"]]["duplicate_vlans"] == []

    @pytest.mark.parametrize("hostname", refmodel.in_scope_wan_edge_hostnames())
    def test_vrf_bindings_canonical(self, hostname: str) -> None:
        """WAN edge routers must use canonical CORP-IT VRF bindings."""
        assert refmodel.vrf_binding_ok(hostname)

    @pytest.mark.parametrize("hostname", refmodel.in_scope_access_hostnames())
    def test_access_vlan_assignments(self, hostname: str) -> None:
        """Access ports must use catalog VLAN IDs without duplicate conflicts."""
        assert refmodel.access_vlan_assignments_ok(hostname)

    def test_assembly_precedence_authoritative(self) -> None:
        """Assembly precedence must disable legacy source consultation."""
        assert refmodel.authoritative_precedence()

    def test_in_scope_count_unchanged(self) -> None:
        """Golden in-scope device count must remain unchanged during remediation."""
        assert len(refmodel.in_scope_devices()) == refmodel.IN_SCOPE_COUNT

    def test_evidence_stable_after_rerun(self, evidence: dict) -> None:
        """Evidence export must remain stable when evidence reruns without reset."""
        first = canonical_evidence(evidence)
        second_run = run_stage("evidence", reset=False)
        assert_stage_ok(second_run, "evidence")
        again = canonical_evidence(load_output("migration_evidence.json"))
        assert again == first


class TestWave3TrunkGateway:
    """Validate trunk conformance, gateway placement, and rendered device bundles."""

    @pytest.fixture(autouse=True)
    def _require_trunk_authoritative(self) -> None:
        assert refmodel.config_authoritative_m2(), "trunk configuration not yet authoritative"

    def test_trunk_export_invariants(self, trunk_doc: dict) -> None:
        """Pipeline trunk export must satisfy sealed schema and dependency invariants."""
        assert refmodel.trunk_export_invariants(trunk_doc) == []

    def test_all_trunk_checks_pass(self, trunk_doc: dict) -> None:
        """Every in-scope device row in trunk_conformance.json must pass."""
        assert refmodel.all_trunk_pass(trunk_doc)
        assert len(trunk_doc["devices"]) == refmodel.IN_SCOPE_COUNT

    def test_trunk_link_count(self, trunk_doc: dict) -> None:
        """Trunk export must report the contract trunk link count."""
        assert trunk_doc["trunk_link_count"] == TRUNK_LINK_COUNT

    def test_rendered_bundle_count(self, rendered_dir: list) -> None:
        """Render stage must emit one bundle per in-scope device."""
        names = {p.name for p in rendered_dir}
        expected = {f"{h}.conf" for h in refmodel.in_scope_hostnames()}
        assert names == expected
        assert len(names) == refmodel.IN_SCOPE_COUNT

    @pytest.mark.parametrize("bind", refmodel.gateway_bindings(), ids=lambda b: str(b["vlan_id"]))
    def test_gateway_on_distribution(self, bind: dict) -> None:
        """Gateway VIPs from gateway_bindings.yaml must appear on distribution SVIs."""
        assert refmodel.gateway_on_distribution(bind)

    def test_violations_seed_cleared(self) -> None:
        """violations_seed.yaml must use the contract schema and list no device mappings."""
        seed = refmodel.load_yaml("trunks/violations_seed.yaml")
        assert seed.get("schema_version") == "apexora-trunk-violations-1"
        assert seed.get("violations") == []

    @pytest.mark.parametrize("hostname", refmodel.in_scope_hostnames())
    def test_rendered_no_trunk_all(self, hostname: str) -> None:
        """Rendered bundles must not contain trunk-all allow-lists."""
        path = OUTPUT / "rendered" / f"{hostname}.conf"
        text = path.read_text(encoding="utf-8")
        assert "switchport trunk allowed vlan all" not in text


class TestWave3AntiCheat:
    """Behavior-based anti-cheating: pipeline must reflect live configuration mutations."""

    def test_mutation_legacy_consultation_changes_evidence(self) -> None:
        """Re-enabling legacy consultation must surface legacy sources in evidence."""
        assert refmodel.config_authoritative_m1()
        rel = "configs/assembly/source_precedence.yaml"
        original = (ENV / rel).read_text(encoding="utf-8")
        data = yaml.safe_load(original)
        data["consult_legacy_when_present"] = True
        write_config(rel, yaml.dump(data, sort_keys=False))
        refmodel.clear_caches()
        try:
            result = _run_no_reset("evidence")
            assert_stage_ok(result, "evidence")
            doc = load_output("migration_evidence.json")
            assert any(row.get("legacy_sources_consulted") for row in doc["devices"])
            assert refmodel.authoritative_precedence() is False
        finally:
            write_config(rel, original)
            refmodel.clear_caches()
            _run_no_reset("evidence")

    def test_mutation_access_legacy_vlan_fails_vlan_check(self) -> None:
        """Injecting a legacy access VLAN must fail vlan-check for that host."""
        assert refmodel.config_authoritative_m1()
        hostname = refmodel.in_scope_access_hostnames()[0]
        conf_path = refmodel.device_running_conf(hostname, "access")
        assert conf_path is not None
        rel = str(conf_path.relative_to(ENV))
        original = conf_path.read_text(encoding="utf-8")
        mutated = re.sub(
            r"switchport access vlan \d+",
            "switchport access vlan 120",
            original,
            count=1,
        )
        assert mutated != original
        write_config(rel, mutated)
        refmodel.clear_caches()
        try:
            result = _run_no_reset("vlan-check")
            assert_stage_ok(result, "vlan-check")
            doc = load_output("vlan_conformance.json")
            row = next(r for r in doc["devices"] if r["hostname"] == hostname)
            assert row["pass"] is False
            assert any("legacy_vlan" in v for v in row["violations"])
        finally:
            write_config(rel, original)
            refmodel.clear_caches()
            _run_no_reset("vlan-check")

    def test_mutation_trunk_all_fails_trunk_check(self) -> None:
        """Injecting trunk-all on an access uplink must fail trunk-check."""
        assert refmodel.config_authoritative_m2()
        hostname = refmodel.in_scope_access_hostnames()[0]
        conf_path = refmodel.device_running_conf(hostname, "access")
        assert conf_path is not None
        rel = str(conf_path.relative_to(ENV))
        original = conf_path.read_text(encoding="utf-8")
        if "switchport trunk allowed vlan all" in original:
            mutated = original
        else:
            mutated = original + "\nswitchport trunk allowed vlan all\n"
        write_config(rel, mutated)
        refmodel.clear_caches()
        try:
            result = _run_no_reset("vlan-check", "trunk-check")
            assert_stage_ok(result, "trunk-check")
            doc = load_output("trunk_conformance.json")
            row = next(r for r in doc["devices"] if r["hostname"] == hostname)
            assert "trunk_all_vlans" in row["violations"]
            assert row["pass"] is False
        finally:
            write_config(rel, original)
            refmodel.clear_caches()
            _run_no_reset("vlan-check", "trunk-check")

    def test_mutation_residual_seed_fails_trunk_check(self) -> None:
        """Residual violations_seed mappings remain open defects until cleared."""
        assert refmodel.config_authoritative_m2()
        seed_path = "trunks/violations_seed.yaml"
        original = (ENV / seed_path).read_text(encoding="utf-8")
        sample_host = refmodel.in_scope_access_hostnames()[0]
        write_config(
            seed_path,
            "schema_version: apexora-trunk-violations-1\n"
            "violations:\n"
            f"  - device: {sample_host}\n"
            "    interface: TenGigabitEthernet1/1/1\n"
            "    issue: trunk_all_vlans\n",
        )
        refmodel.clear_caches()
        try:
            result = _run_no_reset("vlan-check", "trunk-check")
            assert_stage_ok(result, "trunk-check")
            doc = load_output("trunk_conformance.json")
            row = next(r for r in doc["devices"] if r["hostname"] == sample_host)
            assert "trunk_all_vlans" in row["violations"]
            assert row["pass"] is False
            assert refmodel.trunk_authoritative() is False
        finally:
            write_config(seed_path, original)
            refmodel.clear_caches()
            _run_no_reset("vlan-check", "trunk-check")

    def test_mutation_legacy_acl_fails_acl_check(self) -> None:
        """Injecting a retired ACL name must fail acl-check for that host."""
        assert refmodel.config_authoritative_m2()
        assert refmodel.acl_authoritative()
        hostname = EXPECTED_VALIDATION_SCOPE[0]
        row = next(d for d in refmodel.device_rows() if d["hostname"] == hostname)
        conf_path = refmodel.device_running_conf(hostname, row["role"])
        assert conf_path is not None
        rel = str(conf_path.relative_to(ENV))
        original = conf_path.read_text(encoding="utf-8")
        mutated = original + "\nip access-group ACL-EDGE-LEGACY in\n"
        write_config(rel, mutated)
        refmodel.clear_caches()
        try:
            result = _run_no_reset("vlan-check", "trunk-check", "acl-check")
            assert_stage_ok(result, "acl-check")
            doc = load_output("acl_conformance.json")
            out = next(r for r in doc["devices"] if r["hostname"] == hostname)
            assert out["pass"] is False
            assert "ACL-EDGE-LEGACY" in out["violations"]
        finally:
            write_config(rel, original)
            refmodel.clear_caches()
            _run_no_reset("vlan-check", "trunk-check", "acl-check")

    def test_mutation_vlan_failure_propagates_to_trunk(self) -> None:
        """A failed VLAN decision must surface as upstream_vlan_failed on trunk-check."""
        assert refmodel.config_authoritative_m1()
        hostname = refmodel.in_scope_access_hostnames()[0]
        conf_path = refmodel.device_running_conf(hostname, "access")
        assert conf_path is not None
        rel = str(conf_path.relative_to(ENV))
        original = conf_path.read_text(encoding="utf-8")
        mutated = re.sub(
            r"switchport access vlan \d+",
            "switchport access vlan 120",
            original,
            count=1,
        )
        write_config(rel, mutated)
        refmodel.clear_caches()
        try:
            result = _run_no_reset("vlan-check", "trunk-check")
            assert_stage_ok(result, "trunk-check")
            doc = load_output("trunk_conformance.json")
            row = next(r for r in doc["devices"] if r["hostname"] == hostname)
            assert "upstream_vlan_failed" in row["violations"]
            assert row["pass"] is False
        finally:
            write_config(rel, original)
            refmodel.clear_caches()
            _run_no_reset("vlan-check", "trunk-check")


@pytest.fixture
def _acl_gate() -> None:
    assert refmodel.config_authoritative_m2(), "stages 1-2 not authoritative"
    assert refmodel.acl_authoritative(), "ACL configuration not yet authoritative"


@pytest.fixture
def _wave_gate() -> None:
    assert refmodel.config_authoritative_m2(), "stages 1-2 not authoritative"
    assert refmodel.wave_authoritative(), "wave configuration not yet authoritative"


@pytest.fixture
def _rollback_gate() -> None:
    assert refmodel.config_authoritative_m3(), "deployment configuration not yet authoritative"


class TestWave3AclWaveRollback:
    """Validate ACL alignment, wave manifests, and rollback bundle indexing."""

    def test_immutable_validation_scope_cardinality(self, acl_doc: dict, _acl_gate: None) -> None:
        """Pipeline, oracle, and tests share the immutable 48-host validation scope."""
        hosts = refmodel.validation_scope_hostnames()
        assert hosts == EXPECTED_VALIDATION_SCOPE
        assert len(hosts) == refmodel.VALIDATION_SCOPE_COUNT
        assert refmodel.CANARY_ANCHOR in hosts
        assert len(acl_doc["devices"]) == refmodel.VALIDATION_SCOPE_COUNT
        assert {row["hostname"] for row in acl_doc["devices"]} == set(EXPECTED_VALIDATION_SCOPE)

    def test_acl_export_invariants(self, acl_doc: dict, _acl_gate: None) -> None:
        """ACL export must satisfy sealed schema and validation-scope invariants."""
        assert refmodel.acl_export_invariants(acl_doc) == []
        assert len(acl_doc["devices"]) == len(refmodel.validation_scope_hostnames())

    def test_all_acl_checks_pass(self, acl_doc: dict, _acl_gate: None) -> None:
        """Every validation-scope device must pass ACL conformance."""
        assert refmodel.all_acl_pass(acl_doc)

    def test_policy_catalog_count(self, acl_doc: dict, _acl_gate: None) -> None:
        """ACL export must report the contract policy catalog size."""
        assert acl_doc["policy_catalog_count"] == POLICY_CATALOG_COUNT

    def test_wave_export_invariants(self, wave_doc: dict, _wave_gate: None) -> None:
        """Wave readiness export must satisfy sealed canary and coverage invariants."""
        assert refmodel.wave_export_invariants(wave_doc) == []
        assert wave_doc["canary_first"] is True
        assert wave_doc["legacy_hooks_present"] is False
        assert wave_doc["missing_devices"] == []

    def test_canary_precedes_regional_batches(self, wave_doc: dict, _wave_gate: None) -> None:
        """Wave phases must begin with canary before regional batches."""
        phases = [p.get("phase_id") for p in wave_doc["phases"]]
        assert phases[0] == "canary"
        assert "amer_batch" in phases
        assert "emea_batch" in phases
        assert "apac_batch" in phases

    def test_regional_order_amer_emea_apac(self, wave_doc: dict, _wave_gate: None) -> None:
        """Regional rollout order must follow amer, emea, apac."""
        assert wave_doc["regional_order"] == refmodel.REGIONAL_ORDER

    def test_post_deploy_hook_active(self, wave_doc: dict, _wave_gate: None) -> None:
        """Wave manifest must wire the active post-deploy validation hook."""
        assert wave_doc["post_deploy_hook"] == refmodel.ACTIVE_HOOK

    def test_rollback_export_invariants(self, rollback_doc: dict, _rollback_gate: None) -> None:
        """Rollback manifest must satisfy sealed scope and bundle invariants."""
        assert refmodel.rollback_export_invariants(rollback_doc) == []
        assert rollback_doc["device_count"] == refmodel.VALIDATION_SCOPE_COUNT
        assert rollback_doc["missing_hosts"] == []

    @pytest.mark.parametrize("hostname", EXPECTED_VALIDATION_SCOPE)
    def test_each_validation_scope_device_indexed(
        self, rollback_doc: dict, hostname: str, _rollback_gate: None
    ) -> None:
        """Rollback manifest must include a bundle row for each validation-scope host."""
        hosts = {b["hostname"] for b in rollback_doc["bundles"]}
        assert hostname in hosts

    @pytest.mark.parametrize("hostname", EXPECTED_VALIDATION_SCOPE)
    def test_each_rollback_record(self, rollback_doc: dict, hostname: str, _rollback_gate: None) -> None:
        """Every validation-scope bundle must have resolvable forward/rollback artifacts and active hook."""
        row = next(b for b in rollback_doc["bundles"] if b["hostname"] == hostname)
        assert row["forward"], f"{hostname} missing forward path"
        assert row["rollback"], f"{hostname} missing rollback path"
        assert refmodel.forward_path_authoritative(row["forward"])
        assert refmodel.forward_path_authoritative(row["rollback"])
        assert row["forward_exists"] is True
        assert row["rollback_exists"] is True
        assert refmodel.resolve_env_path(row["forward"]).is_file()
        assert refmodel.resolve_env_path(row["rollback"]).is_file()
        assert row["validation_command"] == refmodel.validation_command_for(hostname)
        assert refmodel.validation_command_matches(hostname, row["validation_command"])
        assert refmodel.LEGACY_HOOK not in row["validation_command"]

    def test_legacy_hooks_absent(self, _wave_gate: None) -> None:
        """Canary and wave manifests must not reference legacy validation hooks."""
        assert refmodel.legacy_hooks_present() is False

    def test_deprecated_hook_script_removed(self, _wave_gate: None) -> None:
        """Deprecated pre-validate hook script must be removed from the environment."""
        assert not (refmodel.ENV / refmodel.LEGACY_HOOK).is_file()

    def test_rollback_snapshots_carry_pre_change_marker(self, rollback_doc: dict, _rollback_gate: None) -> None:
        """Rollback snapshots must be stamped as pre-wave3 boundary artifacts."""
        for row in rollback_doc["bundles"]:
            rb = refmodel.resolve_env_path(row["rollback"]).read_text(encoding="utf-8")
            assert rb.startswith(refmodel.PRE_WAVE3_SNAPSHOT_MARKER)

    def test_static_validation_scope_config(self) -> None:
        """On-disk validation scope must match the verifier golden host inventory."""
        scope = refmodel.load_yaml("inventory/wave3_validation_scope.yaml")
        assert scope.get("host_count") == refmodel.VALIDATION_SCOPE_COUNT
        assert scope.get("hostnames") == EXPECTED_VALIDATION_SCOPE

    @pytest.mark.parametrize("hostname", EXPECTED_VALIDATION_SCOPE)
    def test_rollback_snapshot_is_pre_change(
        self, rollback_doc: dict, hostname: str, _rollback_gate: None
    ) -> None:
        """Rollback snapshots must be pre-change artifacts, not post-migration copies."""
        row = next(b for b in rollback_doc["bundles"] if b["hostname"] == hostname)
        assert refmodel.rollback_snapshot_is_pre_change(hostname, row["forward"], row["rollback"])
        assert row["rollback_exists"] is True

    def test_validation_scope_includes_canary_anchor(self, acl_doc: dict, _acl_gate: None) -> None:
        """ACL export must include the immutable canary distribution anchor."""
        hosts = {row["hostname"] for row in acl_doc["devices"]}
        assert refmodel.CANARY_ANCHOR in hosts


class TestWave3RollbackPathMutation:
    """Negative checks for non-durable rollback forward paths."""

    def test_mutation_rendered_forward_path_rejected(self) -> None:
        """Rollback audit must reject forward paths that point at rendered export trees."""
        assert refmodel.config_authoritative_m3()
        hostname = EXPECTED_VALIDATION_SCOPE[0]
        bundles_path = "deployment/rollback/bundles.yaml"
        original = (refmodel.ENV / bundles_path).read_text(encoding="utf-8")
        bundles = refmodel.load_yaml(bundles_path)
        bundles.setdefault("bundles", {})[hostname] = {
            "forward": f"output/rendered/{hostname}.conf",
            "rollback": f"backups/pre_wave3/{hostname}.conf.snapshot",
            "validation_command": refmodel.validation_command_for(hostname),
        }
        write_config(
            bundles_path,
            yaml.dump(bundles, sort_keys=False),
        )
        refmodel.clear_caches()
        try:
            result = _run_no_reset(
                "vlan-check",
                "trunk-check",
                "acl-check",
                "render",
                "wave-plan",
                "rollback-audit",
            )
            assert_stage_ok(result, "rollback-audit")
            doc = load_output("rollback_bundle_manifest.json")
            row = next(b for b in doc["bundles"] if b["hostname"] == hostname)
            assert row["forward_exists"] is False
            assert refmodel.rollback_authoritative() is False
        finally:
            write_config(bundles_path, original)
            refmodel.clear_caches()
            _run_no_reset(
                "vlan-check",
                "trunk-check",
                "acl-check",
                "render",
                "wave-plan",
                "rollback-audit",
            )
