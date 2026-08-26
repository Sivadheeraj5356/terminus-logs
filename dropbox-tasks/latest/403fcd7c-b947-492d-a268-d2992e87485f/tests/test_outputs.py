import csv
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


APP = Path("/app")
DOSSIER = APP / "dossier"
RECORDS = APP / "records"

EXPECTED_FILES = {
    "decision/failover-verdict.json",
    "decision/start-order.tsv",
    "decision/hold-list.tsv",
    "decision/rollback-window.json",
    "evidence/health-ledger.tsv",
    "evidence/quorum-ledger.tsv",
    "evidence/fencing-ledger.tsv",
    "evidence/mount-ledger.tsv",
    "evidence/route-ledger.tsv",
    "evidence/credential-ledger.tsv",
    "attestations/dependency-attestation.json",
    "attestations/quorum-attestation.json",
    "attestations/fencing-attestation.json",
    "attestations/route-attestation.json",
    "attestations/rollback-attestation.json",
    "index/incident-index.json",
}

ORIGINAL_RECORDS = {
    path.name: path.read_text(encoding="utf-8")
    for path in RECORDS.glob("*.tsv")
}


def read_tsv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_entrypoint(record_overrides=None):
    """Reset records, optionally swap in a same-contract estate, and regenerate the dossier."""
    for name, content in ORIGINAL_RECORDS.items():
        (RECORDS / name).write_text(content, encoding="utf-8")
    for name, content in (record_overrides or {}).items():
        (RECORDS / name).write_text(content, encoding="utf-8")
    solver = APP / "solve.sh"
    assert solver.exists(), "/app/solve.sh is required"
    mode = solver.stat().st_mode
    assert mode & stat.S_IXUSR, "/app/solve.sh must be executable"
    shutil.rmtree(DOSSIER, ignore_errors=True)
    result = subprocess.run(
        [str(solver)],
        cwd=str(APP),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_entrypoint_regenerates_all_required_artifacts():
    """The reusable entrypoint creates exactly the public sixteen-file dossier."""
    run_entrypoint()
    found = {str(path.relative_to(DOSSIER)).replace(os.sep, "/") for path in DOSSIER.rglob("*") if path.is_file()}
    assert found == EXPECTED_FILES


def test_failover_verdict_selects_the_only_safe_target():
    """The verdict binds the current epoch, root service, target host, and readiness status."""
    run_entrypoint()
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    assert verdict == {
        "earliest_blocker": "NONE",
        "incident_epoch": 1700,
        "old_active_host": "node-a",
        "root_service": "api",
        "target_host": "node-c",
        "verdict": "FAILOVER_READY",
    }


def test_health_and_quorum_reject_stale_local_evidence():
    """Node-b is healthy only under a stale epoch, while node-c has current quorum."""
    run_entrypoint()
    health = {row["host_id"]: row for row in read_tsv(DOSSIER / "evidence/health-ledger.tsv")}
    quorum = {row["candidate_host"]: row for row in read_tsv(DOSSIER / "evidence/quorum-ledger.tsv")}
    assert health["node-b"]["current"] == "NO"
    assert health["node-b"]["eligible"] == "NO"
    assert quorum["node-b"]["quorum_status"] == "FAIL"
    assert quorum["node-c"] == {
        "candidate_host": "node-c",
        "reachable_votes": "2",
        "threshold": "2",
        "quorum_status": "PASS",
    }


def test_fencing_and_mount_ledgers_prove_exclusive_storage():
    """The old holder is fenced before the mounted database service starts on the target."""
    run_entrypoint()
    fencing = read_tsv(DOSSIER / "evidence/fencing-ledger.tsv")
    mounts = read_tsv(DOSSIER / "evidence/mount-ledger.tsv")
    assert fencing == [{"volume_id": "orders-vol", "previous_holder": "node-a", "fence_status": "FENCED"}]
    assert mounts == [{"service_id": "db", "volume_id": "orders-vol", "target_host": "node-c", "mount_status": "PASS"}]


def test_credentials_dependency_order_and_holds_are_consistent():
    """Credential validity blocks admin while the remaining service chain starts in dependency order."""
    run_entrypoint()
    credentials = {row["service_id"]: row["credential_status"] for row in read_tsv(DOSSIER / "evidence/credential-ledger.tsv")}
    start = read_tsv(DOSSIER / "decision/start-order.tsv")
    hold = read_tsv(DOSSIER / "decision/hold-list.tsv")
    assert credentials == {"admin": "FAIL", "api": "PASS", "db": "PASS", "worker": "PASS"}
    assert start == [
        {"order": "1", "service_id": "db", "target_host": "node-c"},
        {"order": "2", "service_id": "api", "target_host": "node-c"},
        {"order": "3", "service_id": "worker", "target_host": "node-c"},
    ]
    assert hold == [{"service_id": "admin", "reason": "CREDENTIAL_BLOCKED"}]


def test_route_exposure_respects_started_and_held_services():
    """Public route exposure moves only the started API service and suppresses held admin."""
    run_entrypoint()
    routes = {row["service_id"]: row for row in read_tsv(DOSSIER / "evidence/route-ledger.tsv")}
    assert routes["api"] == {
        "service_id": "api",
        "advertised_host": "node-c",
        "advertised_scope": "public",
        "route_status": "PASS",
    }
    assert routes["admin"] == {
        "service_id": "admin",
        "advertised_host": "NONE",
        "advertised_scope": "NONE",
        "route_status": "HELD",
    }


def test_rollback_window_has_no_downstream_blocker():
    """The rollback artifact remains available only because no public blocker is present."""
    run_entrypoint()
    rollback = read_json(DOSSIER / "decision/rollback-window.json")
    assert rollback == {"blockers": [], "rollback_status": "AVAILABLE", "target_host": "node-c"}


def test_attestations_cite_the_required_evidence_surfaces():
    """Each safety attestation names the same target and cites the ledgers it depends on."""
    run_entrypoint()
    expected = {
        "dependency-attestation.json": ("PASS", "decision/start-order.tsv;decision/hold-list.tsv;evidence/credential-ledger.tsv;evidence/mount-ledger.tsv"),
        "quorum-attestation.json": ("PASS", "evidence/quorum-ledger.tsv;evidence/health-ledger.tsv"),
        "fencing-attestation.json": ("PASS", "evidence/fencing-ledger.tsv;evidence/mount-ledger.tsv"),
        "route-attestation.json": ("PASS", "evidence/route-ledger.tsv;decision/hold-list.tsv"),
        "rollback-attestation.json": ("AVAILABLE", "decision/rollback-window.json;evidence/route-ledger.tsv;evidence/mount-ledger.tsv"),
    }
    for name, (status, evidence) in expected.items():
        attestation = read_json(DOSSIER / "attestations" / name)
        assert attestation["incident_epoch"] == 1700
        assert attestation["target_host"] == "node-c"
        assert attestation["status"] == status
        assert attestation["evidence"] == evidence


def test_incident_index_binds_every_non_index_artifact_by_digest():
    """The index commits to normalized bytes for every other dossier artifact."""
    run_entrypoint()
    index = read_json(DOSSIER / "index/incident-index.json")
    assert index["artifact_count"] == 16
    assert index["incident_epoch"] == 1700
    assert index["root_service"] == "api"
    assert index["target_host"] == "node-c"
    assert index["verdict"] == "FAILOVER_READY"
    expected_artifacts = EXPECTED_FILES - {"index/incident-index.json"}
    assert set(index["artifacts"]) == expected_artifacts
    for relative, digest in index["artifacts"].items():
        assert digest == sha256(DOSSIER / relative)


def test_index_dependency_edges_cover_cross_artifact_invariants():
    """The index records the mandatory cross-artifact dependency edges."""
    run_entrypoint()
    index = read_json(DOSSIER / "index/incident-index.json")
    edges = {tuple(edge) for edge in index["dependency_edges"]}
    for relative in EXPECTED_FILES - {"index/incident-index.json"}:
        assert ("index/incident-index.json", relative) in edges
    required = {
        ("attestations/dependency-attestation.json", "decision/start-order.tsv"),
        ("attestations/dependency-attestation.json", "decision/hold-list.tsv"),
        ("attestations/fencing-attestation.json", "evidence/fencing-ledger.tsv"),
        ("attestations/quorum-attestation.json", "evidence/quorum-ledger.tsv"),
        ("attestations/rollback-attestation.json", "decision/rollback-window.json"),
        ("attestations/route-attestation.json", "evidence/route-ledger.tsv"),
        ("decision/failover-verdict.json", "attestations/quorum-attestation.json"),
        ("decision/failover-verdict.json", "attestations/fencing-attestation.json"),
    }
    expected = required | {("index/incident-index.json", relative) for relative in EXPECTED_FILES - {"index/incident-index.json"}}
    assert edges == expected


def test_json_files_are_sorted_two_space_and_newline_terminated():
    """JSON artifacts use the public normalized byte form."""
    run_entrypoint()
    for path in sorted(DOSSIER.rglob("*.json")):
        raw = path.read_bytes()
        assert raw.endswith(b"\n")
        parsed = json.loads(raw.decode("utf-8"))
        expected = json.dumps(parsed, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        assert raw == expected


def test_canonical_row_ordering_is_stable():
    """TSV ledgers and decision rows follow the public canonical ordering rules."""
    run_entrypoint()
    health_hosts = [row["host_id"] for row in read_tsv(DOSSIER / "evidence/health-ledger.tsv")]
    quorum_hosts = [row["candidate_host"] for row in read_tsv(DOSSIER / "evidence/quorum-ledger.tsv")]
    credential_services = [row["service_id"] for row in read_tsv(DOSSIER / "evidence/credential-ledger.tsv")]
    route_services = [row["service_id"] for row in read_tsv(DOSSIER / "evidence/route-ledger.tsv")]
    start_orders = [int(row["order"]) for row in read_tsv(DOSSIER / "decision/start-order.tsv")]
    assert health_hosts == sorted(health_hosts)
    assert quorum_hosts == sorted(quorum_hosts)
    assert credential_services == sorted(credential_services)
    assert route_services == sorted(route_services)
    assert start_orders == sorted(start_orders)


def test_artifact_mutation_invalidates_the_index_digest():
    """A stale or copied index cannot remain valid after a late edit to a bound artifact."""
    run_entrypoint()
    target = DOSSIER / "evidence/quorum-ledger.tsv"
    before = read_json(DOSSIER / "index/incident-index.json")["artifacts"]["evidence/quorum-ledger.tsv"]
    target.write_text(target.read_text(encoding="utf-8").replace("PASS", "FAIL", 1), encoding="utf-8")
    assert sha256(target) != before


def test_copied_quorum_attestation_is_detectably_inconsistent():
    """A copied quorum attestation cannot claim a target different from the selected verdict."""
    run_entrypoint()
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    attestation_path = DOSSIER / "attestations/quorum-attestation.json"
    attestation = read_json(attestation_path)
    attestation["target_host"] = "node-b"
    attestation_path.write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert read_json(attestation_path)["target_host"] != verdict["target_host"]


def test_replacement_records_without_current_health_block_failover():
    """A hidden same-schema estate with no current eligible standby reports no healthy target."""
    run_entrypoint(
        {
            "health.tsv": (
                "host_id\tstatus\tevidence_epoch\n"
                "node-a\tDOWN\t1700\n"
                "node-b\tUP\t1699\n"
                "node-c\tDOWN\t1700\n"
                "node-d\tDOWN\t1700\n"
            )
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    assert verdict["verdict"] == "NO_SAFE_FAILOVER"
    assert verdict["target_host"] == ""
    assert verdict["earliest_blocker"] == "NO_HEALTHY_TARGET"


def test_replacement_records_with_healthy_but_partitioned_targets_report_quorum():
    """Healthy standby hosts are still unsafe when current quorum evidence is insufficient."""
    run_entrypoint(
        {
            "quorum.tsv": (
                "candidate_host\tvoter_host\treachable\tevidence_epoch\n"
                "node-c\tnode-c\tYES\t1700\n"
                "node-c\tnode-d\tNO\t1700\n"
                "node-d\tnode-d\tYES\t1700\n"
            )
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    assert verdict["verdict"] == "NO_SAFE_FAILOVER"
    assert verdict["target_host"] == ""
    assert verdict["earliest_blocker"] == "QUORUM_BLOCKED"


def test_replacement_records_choose_a_different_safe_standby():
    """A dossier hardcoded to the sample target fails when priority selects another safe host."""
    run_entrypoint(
        {
            "hosts.tsv": (
                "host_id\tpriority\thost_group\n"
                "node-a\t1\tblue\n"
                "node-b\t4\tblue\n"
                "node-c\t3\tgreen\n"
                "node-d\t2\tgreen\n"
            ),
            "quorum.tsv": (
                "candidate_host\tvoter_host\treachable\tevidence_epoch\n"
                "node-c\tnode-c\tYES\t1700\n"
                "node-c\tnode-d\tYES\t1700\n"
                "node-d\tnode-c\tYES\t1700\n"
                "node-d\tnode-d\tYES\t1700\n"
            ),
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    start = read_tsv(DOSSIER / "decision/start-order.tsv")
    quorum = {row["candidate_host"]: row for row in read_tsv(DOSSIER / "evidence/quorum-ledger.tsv")}
    assert verdict["target_host"] == "node-d"
    assert verdict["verdict"] == "FAILOVER_READY"
    assert {row["target_host"] for row in start} == {"node-d"}
    assert quorum["node-d"]["quorum_status"] == "PASS"


def test_replacement_records_with_unfenceable_storage_report_fencing():
    """A selected target with quorum cannot activate while the old storage lease cannot be fenced."""
    run_entrypoint(
        {
            "leases.tsv": (
                "volume_id\tholder_host\tauthority\tlease_state\tevidence_epoch\tcan_fence\n"
                "orders-vol\tnode-a\tlease-17\tactive\t1700\tNO\n"
            )
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    fencing = read_tsv(DOSSIER / "evidence/fencing-ledger.tsv")
    assert fencing[0]["fence_status"] == "FAIL"
    assert verdict["target_host"] == "node-c"
    assert verdict["earliest_blocker"] == "FENCING_BLOCKED"


def test_replacement_records_with_irreversible_started_service_report_rollback():
    """Rollback blockers invalidate a locally safe cutover after service activation is planned."""
    run_entrypoint(
        {
            "services.tsv": (
                "service_id\tpriority\trequires_mount\troute_scope\tcredential_id\tirreversible_barrier\n"
                "db\t1\torders-vol\tinternal\tcred-db\tNO\n"
                "api\t2\tNONE\tpublic\tcred-api\tYES\n"
                "worker\t3\tNONE\tinternal\tcred-api\tNO\n"
                "admin\t4\tNONE\tprivate\tcred-admin\tNO\n"
            )
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    rollback = read_json(DOSSIER / "decision/rollback-window.json")
    assert rollback["rollback_status"] == "BLOCKED"
    assert "IRREVERSIBLE_SERVICE:api" in rollback["blockers"]
    assert verdict["earliest_blocker"] == "ROLLBACK_BLOCKED"


def test_replacement_records_with_expired_root_credential_report_credential():
    """Credential validity windows and host groups are load-bearing for service activation."""
    run_entrypoint(
        {
            "credentials.tsv": (
                "credential_id\thost_group\tnot_before\tnot_after\trevoked\n"
                "cred-db\tgreen\t1600\t1800\tNO\n"
                "cred-api\tgreen\t1600\t1699\tNO\n"
                "cred-admin\tgreen\t1600\t1800\tNO\n"
            )
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    credentials = {row["service_id"]: row["credential_status"] for row in read_tsv(DOSSIER / "evidence/credential-ledger.tsv")}
    assert credentials["api"] == "FAIL"
    assert verdict["earliest_blocker"] == "CREDENTIAL_BLOCKED"


def test_replacement_records_with_dependency_ancestor_held_report_dependency():
    """A service remains held when an otherwise healthy dependency ancestor cannot start."""
    run_entrypoint(
        {
            "credentials.tsv": (
                "credential_id\thost_group\tnot_before\tnot_after\trevoked\n"
                "cred-db\tgreen\t1600\t1699\tNO\n"
                "cred-api\tgreen\t1600\t1800\tNO\n"
                "cred-admin\tgreen\t1600\t1800\tNO\n"
            )
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    holds = {row["service_id"]: row["reason"] for row in read_tsv(DOSSIER / "decision/hold-list.tsv")}
    dependency_attestation = read_json(DOSSIER / "attestations/dependency-attestation.json")
    assert holds["db"] == "CREDENTIAL_BLOCKED"
    assert holds["api"] == "DEPENDENCY_HELD"
    assert verdict["earliest_blocker"] == "DEPENDENCY_HELD"
    assert dependency_attestation["status"] == "PASS"


def test_replacement_records_with_route_scope_mismatch_report_route():
    """Route scope mismatches block an otherwise safe started service exposure."""
    run_entrypoint(
        {
            "routes.tsv": (
                "service_id\tallowed_scope\tcurrent_host\n"
                "api\tprivate\tnode-a\n"
                "admin\tprivate\tnode-a\n"
            )
        }
    )
    verdict = read_json(DOSSIER / "decision/failover-verdict.json")
    holds = {row["service_id"]: row["reason"] for row in read_tsv(DOSSIER / "decision/hold-list.tsv")}
    routes = {row["service_id"]: row for row in read_tsv(DOSSIER / "evidence/route-ledger.tsv")}
    route_attestation = read_json(DOSSIER / "attestations/route-attestation.json")
    dependency_attestation = read_json(DOSSIER / "attestations/dependency-attestation.json")
    assert holds["api"] == "ROUTE_BLOCKED"
    assert routes["api"]["route_status"] == "FAIL"
    assert route_attestation["status"] == "FAIL"
    assert dependency_attestation["status"] == "PASS"
    assert verdict["earliest_blocker"] == "ROUTE_BLOCKED"


def test_attestation_statuses_follow_unsafe_ledger_state():
    """Attestation status fields change with the ledger state they cite."""
    run_entrypoint(
        {
            "leases.tsv": (
                "volume_id\tholder_host\tauthority\tlease_state\tevidence_epoch\tcan_fence\n"
                "orders-vol\tnode-a\tlease-17\tactive\t1700\tNO\n"
            )
        }
    )
    attestation = read_json(DOSSIER / "attestations/fencing-attestation.json")
    assert attestation["status"] == "FAIL"


def test_replacement_records_report_every_rollback_blocker_string():
    """Rollback blocker serialization covers old-host, route, storage, and irreversible barriers."""
    run_entrypoint(
        {
            "rollback.tsv": (
                "old_host_destroyed\troute_rollback\tstorage_reattach\n"
                "YES\tNO\tNO\n"
            ),
            "services.tsv": (
                "service_id\tpriority\trequires_mount\troute_scope\tcredential_id\tirreversible_barrier\n"
                "db\t1\torders-vol\tinternal\tcred-db\tYES\n"
                "api\t2\tNONE\tpublic\tcred-api\tYES\n"
                "worker\t3\tNONE\tinternal\tcred-api\tNO\n"
                "admin\t4\tNONE\tprivate\tcred-admin\tNO\n"
            ),
        }
    )
    rollback = read_json(DOSSIER / "decision/rollback-window.json")
    assert rollback["blockers"] == [
        "IRREVERSIBLE_SERVICE:api",
        "IRREVERSIBLE_SERVICE:db",
        "OLD_HOST_DESTROYED",
        "ROUTE_ROLLBACK_BLOCKED",
        "STORAGE_REATTACH_BLOCKED",
    ]


def test_replacement_records_keep_dependency_order_despite_input_order():
    """Start ordering follows dependencies and priorities rather than declaration order."""
    run_entrypoint(
        {
            "services.tsv": (
                "service_id\tpriority\trequires_mount\troute_scope\tcredential_id\tirreversible_barrier\n"
                "worker\t3\tNONE\tinternal\tcred-api\tNO\n"
                "api\t2\tNONE\tpublic\tcred-api\tNO\n"
                "admin\t4\tNONE\tprivate\tcred-admin\tNO\n"
                "db\t1\torders-vol\tinternal\tcred-db\tNO\n"
            )
        }
    )
    start = read_tsv(DOSSIER / "decision/start-order.tsv")
    assert [row["service_id"] for row in start] == ["db", "api", "worker"]
