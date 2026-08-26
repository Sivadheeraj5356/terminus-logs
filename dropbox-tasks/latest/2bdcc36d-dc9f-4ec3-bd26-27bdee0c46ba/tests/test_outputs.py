"""Tests for the Merkle CRDT sync stack."""

import json
import subprocess
from pathlib import Path

import pytest

SCENETEST = Path("/app/bin/scenetest")
TESTS_DIR = Path("/app/tests")


def build_scenetest() -> None:
    """Rebuild the Rust scenario harness after agent edits."""
    subprocess.run(
        ["cargo", "build", "--release", "--bin", "scenetest"],
        cwd="/app",
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["install", "-m", "0755", "/app/target/release/scenetest", str(SCENETEST)],
        check=True,
    )


def run_scenario(name: str, seed: int = 42) -> dict:
    """Execute a named scenetest scenario and parse JSON output."""
    build_scenetest()
    proc = subprocess.run(
        [str(SCENETEST), "--scenario", name, "--seed", str(seed)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    payload = proc.stdout.strip()
    assert payload, f"scenetest produced no output: {proc.stderr}"
    return json.loads(payload)


def run_contract_test(test_name: str, source: str) -> None:
    """Compile and execute a temporary Rust integration test under /app/tests."""
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    test_path = TESTS_DIR / f"{test_name}.rs"
    test_path.write_text(source)
    try:
        subprocess.run(
            ["cargo", "test", "--release", "--test", test_name],
            cwd="/app",
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
    finally:
        test_path.unlink(missing_ok=True)


class TestMilestone1:
    """Verify Merkle DAG construction and vector clock embedding."""

    def test_m1_scenario_passes(self):
        """Verify the m1_merkle_dag scenario succeeds end-to-end."""
        result = run_scenario("m1_merkle_dag")
        assert result["passed"] is True, result.get("error", result)

    def test_cross_replica_root_scenario_passes(self):
        """Verify identical logs hash identically across local replica ids."""
        result = run_scenario("m1_cross_replica_root")
        assert result["passed"] is True, result.get("error", result)

    def test_root_hash_nonzero(self):
        """Verify ingested operations produce a non-zero Merkle root."""
        details = run_scenario("m1_merkle_dag")["details"]
        assert details["root_nonzero"] is True

    def test_identical_logs_share_root(self):
        """Verify replicas with identical ops converge to the same root hash."""
        details = run_scenario("m1_merkle_dag")["details"]
        assert details["shared_root"] != "00" * 32

    def test_leaf_embeds_vector_clock(self):
        """Verify the first leaf stores the originating replica clock."""
        details = run_scenario("m1_merkle_dag")["details"]
        assert details["leaf_clock_replica"] >= 1

    def test_merkle_uses_full_opid_tree_order(self):
        """Verify Merkle tree shape follows full OpId ordering, not counter alone."""
        run_contract_test(
            "m1_merkle_order",
            """
use merkle_crdt_sync::{MerkleDag, OpId, Operation, VectorClock};

#[test]
fn cross_replica_counter_tie_breaks_by_replica_id() {
    let mut left = MerkleDag::new(1);
    let mut right = MerkleDag::new(2);

    let low = OpId::new(1, 2);
    let high = OpId::new(2, 1);
    let op_low = Operation::Insert { after: None, id: low, value: 'l' };
    let op_high = Operation::Insert { after: None, id: high, value: 'h' };

    let mut c_low = VectorClock::new();
    c_low.increment(1);
    c_low.increment(1);
    let mut c_high = VectorClock::new();
    c_high.increment(2);

    left.ingest(&op_low, &c_low).expect("left ingest low");
    left.ingest(&op_high, &c_high).expect("left ingest high");
    right.ingest(&op_low, &c_low).expect("right ingest low");
    right.ingest(&op_high, &c_high).expect("right ingest high");

    assert_eq!(left.root_hash(), right.root_hash(), "identical logs must share root");
    assert_ne!(
        left.subtree_hash("L").expect("left L"),
        left.subtree_hash("R").expect("left R"),
        "counter-only ordering would place 2:1 before 1:2 in the left subtree"
    );
}
""",
        )

    def test_diff_paths_minimal_on_leaf_mismatch(self):
        """Verify diff_paths recurses instead of returning only the root path."""
        run_contract_test(
            "m1_diff_minimal",
            """
use merkle_crdt_sync::{MerkleDag, OpId, Operation, VectorClock};

#[test]
fn diff_paths_finds_leaf_not_only_root() {
    let mut local = MerkleDag::new(1);
    let mut remote = MerkleDag::new(2);

    let shared = OpId::new(1, 1);
    let shared_op = Operation::Insert { after: None, id: shared, value: 's' };
    let mut shared_clock = VectorClock::new();
    shared_clock.increment(1);
    local.ingest(&shared_op, &shared_clock).expect("local shared");
    remote.ingest(&shared_op, &shared_clock).expect("remote shared");

    let extra = OpId::new(2, 1);
    let extra_op = Operation::Insert { after: Some(shared), id: extra, value: 'x' };
    let mut extra_clock = VectorClock::new();
    extra_clock.increment(2);
    remote.ingest(&extra_op, &extra_clock).expect("remote extra");

    let paths = remote.diff_paths(&local).expect("diff_paths must succeed");
    assert!(!paths.is_empty(), "roots differ so diff must not be empty");
    assert!(
        paths.iter().any(|p| !p.is_empty()),
        "minimal diff must include a descendant path, not only the root"
    );
}
""",
        )

    @pytest.mark.parametrize("seed", [42, 7])
    def test_identical_replay_stable(self, seed: int):
        """Verify identical-op replay yields matching roots across seeds."""
        build_scenetest()
        proc = subprocess.run(
            [str(SCENETEST), "--scenario", "m1_merkle_dag", "--seed", str(seed)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        result = json.loads(proc.stdout)
        assert result["passed"] is True


class TestMilestone2:
    """Verify anti-entropy reconciles divergent Merkle DAGs."""

    def test_m2_scenario_passes(self):
        """Verify the m2_diff_sync scenario succeeds end-to-end."""
        result = run_scenario("m2_diff_sync")
        assert result["passed"] is True, result.get("error", result)

    def test_required_sync_helpers_are_exercised(self):
        """Verify anti_entropy and merge_operation_log satisfy contract behavior."""
        run_contract_test(
            "m2_sync_contract",
            """
use merkle_crdt_sync::{MerkleDag, OpId, Operation, VectorClock};
use merkle_crdt_sync::sync::{anti_entropy, merge_operation_log};

#[test]
fn anti_entropy_reconciles_remote_dag() {
    let mut local = MerkleDag::new(1);
    let mut remote = MerkleDag::new(2);

    let id = OpId::new(2, 1);
    let op = Operation::Insert { after: None, id, value: 'x' };
    let mut clock = VectorClock::new();
    clock.increment(2);
    remote.ingest(&op, &clock).expect("remote ingest must succeed");

    let moved = anti_entropy(&mut local, &remote).expect("anti_entropy must succeed");
    assert!(moved > 0, "anti_entropy should transfer at least one export");
    assert_eq!(local.root_hash(), remote.root_hash(), "roots must converge");
}

#[test]
fn merge_operation_log_dedups_and_sorts_by_full_opid() {
    let id1 = OpId::new(2, 1);
    let id2 = OpId::new(1, 1);
    let op1 = Operation::Insert { after: None, id: id1, value: 'y' };
    let op2 = Operation::Insert { after: None, id: id2, value: 'x' };
    let mut c1 = VectorClock::new();
    c1.increment(2);
    let mut c2 = VectorClock::new();
    c2.increment(1);

    let mut local = vec![(op1.clone(), c1.clone())];
    let remote = vec![(op1, c1), (op2.clone(), c2.clone())];
    merge_operation_log(&mut local, &remote).expect("merge_operation_log must succeed");

    assert_eq!(local.len(), 2, "duplicate ids must be removed");
    assert_eq!(local[0].0.id(), id2, "full OpId sorting should place replica 1 first");
    assert_eq!(local[1].0.id(), id1);
}
""",
        )

    def test_concurrent_fork_orders_by_opid(self):
        """Verify concurrent head inserts converge to OpId-ordered document xy."""
        details = run_scenario("m2_concurrent_fork")["details"]
        assert details["document"] == "xy"

    def test_interleaved_branches_orders_by_opid(self):
        """Verify nested concurrent branches converge to acbd."""
        details = run_scenario("m2_interleaved_branches")["details"]
        assert details["document"] == "acbd"

    def test_delete_tombstones_propagate(self):
        """Verify delete operations sync and materialize as ac."""
        details = run_scenario("m2_delete_resync")["details"]
        assert details["document"] == "ac"

    def test_divergent_replicas_converge(self):
        """Verify anti-entropy yields identical materialized documents."""
        details = run_scenario("m2_diff_sync")["details"]
        assert details["converged"] is True
        assert len(details["document"]) >= 2

    def test_m1_regression(self):
        """Verify milestone 1 behavior still passes after sync changes."""
        result = run_scenario("m1_merkle_dag")
        assert result["passed"] is True, result.get("error", result)

    def test_cross_replica_root_regression(self):
        """Verify cross-replica Merkle root parity still holds."""
        result = run_scenario("m1_cross_replica_root")
        assert result["passed"] is True, result.get("error", result)

    @pytest.mark.parametrize("seed", [42, 7])
    def test_diff_sync_multiple_seeds(self, seed: int):
        """Verify diff sync succeeds across multiple deterministic seeds."""
        result = run_scenario("m2_diff_sync", seed=seed)
        assert result["passed"] is True, result.get("error", result)


class TestMilestone3:
    """Verify partition stress converges after sequence ordering fix."""

    def test_visible_op_ids_sorted_by_full_opid(self):
        """Verify visible_op_ids returns replica-aware ascending OpId order."""
        run_contract_test(
            "m3_sequence_contract",
            """
use merkle_crdt_sync::{OpId, Operation, SequenceState};

#[test]
fn visible_ids_are_sorted_by_full_opid() {
    let mut seq = SequenceState::new();
    let id_a = OpId::new(2, 1);
    let id_b = OpId::new(1, 1);

    seq.apply(&Operation::Insert { after: None, id: id_a, value: 'y' })
        .expect("insert y should succeed");
    seq.apply(&Operation::Insert { after: None, id: id_b, value: 'x' })
        .expect("insert x should succeed");

    let ids = seq.visible_op_ids();
    assert_eq!(ids, vec![id_b, id_a]);
}

#[test]
fn materialize_breaks_counter_ties_by_replica_id() {
    let mut seq = SequenceState::new();
    let id_a = OpId::new(2, 1);
    let id_b = OpId::new(1, 2);

    seq.apply(&Operation::Insert { after: None, id: id_a, value: 'b' })
        .expect("insert b should succeed");
    seq.apply(&Operation::Insert { after: None, id: id_b, value: 'a' })
        .expect("insert a should succeed");

    assert_eq!(seq.materialize(), "ab");
}
""",
        )

    @pytest.mark.parametrize("seed", [42, 7, 1337, 999, 31415])
    def test_m3_scenario_passes(self, seed: int):
        """Verify m3_partition_stress converges for required seeds."""
        result = run_scenario("m3_partition_stress", seed=seed)
        assert result["passed"] is True, result.get("error", result)

    @pytest.mark.parametrize("seed", [42, 7, 1337, 999, 31415])
    def test_at_least_2000_operations(self, seed: int):
        """Verify the stress harness executes at least 2000 operations."""
        details = run_scenario("m3_partition_stress", seed=seed)["details"]
        assert details["operations"] >= 2000

    @pytest.mark.parametrize("seed", [42, 7, 1337, 999, 31415])
    def test_replicas_converge_after_partitions(self, seed: int):
        """Verify both replicas share document and Merkle root after anti-entropy."""
        details = run_scenario("m3_partition_stress", seed=seed)["details"]
        assert details["converged"] is True
        assert details["text_len"] > 0
        assert details["shared_root"] != "00" * 32

    def test_m2_fork_regression(self):
        """Verify OpId-ordered concurrent fork still passes."""
        details = run_scenario("m2_concurrent_fork")["details"]
        assert details["document"] == "xy"

    def test_m2_interleaved_regression(self):
        """Verify interleaved branch ordering still passes."""
        details = run_scenario("m2_interleaved_branches")["details"]
        assert details["document"] == "acbd"

    def test_m2_delete_regression(self):
        """Verify tombstone resync still passes."""
        details = run_scenario("m2_delete_resync")["details"]
        assert details["document"] == "ac"

    def test_m2_regression(self):
        """Verify diff sync still works after stress-hardening changes."""
        result = run_scenario("m2_diff_sync")
        assert result["passed"] is True, result.get("error", result)
