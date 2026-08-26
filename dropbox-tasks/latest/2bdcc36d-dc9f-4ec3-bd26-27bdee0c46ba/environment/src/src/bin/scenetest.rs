use std::collections::HashMap;

use serde::Serialize;
use sha2::{Digest, Sha256};

use merkle_crdt_sync::merkle::MerkleDag;
use merkle_crdt_sync::operation::{OpId, Operation};
use merkle_crdt_sync::replica::Replica;
use merkle_crdt_sync::sim::{
    delete_id, insert_char, replicate_pair, replay_identical_ops, run_partition_stress,
    PARTITION_STRESS_OPS,
};
use merkle_crdt_sync::vector_clock::VectorClock;

#[derive(Serialize)]
struct ScenarioResult {
    scenario: String,
    passed: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    details: HashMap<String, serde_json::Value>,
}

fn fail(scenario: &str, msg: impl Into<String>) -> ScenarioResult {
    ScenarioResult {
        scenario: scenario.to_string(),
        passed: false,
        error: Some(msg.into()),
        details: HashMap::new(),
    }
}

fn digest_text(text: &str) -> String {
    let hash = Sha256::digest(text.as_bytes());
    hex::encode(hash)
}

fn run_m1_cross_replica(_seed: u64) -> ScenarioResult {
    let scenario = "m1_cross_replica_root";
    let mut left = MerkleDag::new(1);
    let mut right = MerkleDag::new(99);

    let ops = [
        (OpId::new(1, 1), Operation::Insert {
            after: None,
            id: OpId::new(1, 1),
            value: 'p',
        }),
        (OpId::new(2, 1), Operation::Insert {
            after: Some(OpId::new(1, 1)),
            id: OpId::new(2, 1),
            value: 'q',
        }),
        (OpId::new(1, 2), Operation::Insert {
            after: Some(OpId::new(2, 1)),
            id: OpId::new(1, 2),
            value: 'r',
        }),
    ];

    for (id, op) in &ops {
        let mut clock = VectorClock::new();
        clock.increment(id.replica);
        if left.ingest(op, &clock).is_err() {
            return fail(scenario, "left ingest failed");
        }
        if right.ingest(op, &clock).is_err() {
            return fail(scenario, "right ingest failed");
        }
    }

    if left.root_hash() != right.root_hash() {
        return fail(
            scenario,
            "identical operation logs on different replica ids produced different roots",
        );
    }

    let mut details = HashMap::new();
    details.insert("shared_root".into(), serde_json::json!(hex::encode(left.root_hash())));

    ScenarioResult {
        scenario: scenario.to_string(),
        passed: true,
        error: None,
        details,
    }
}

fn run_m1(_seed: u64) -> ScenarioResult {
    let scenario = "m1_merkle_dag";
    let mut replica = Replica::new(1);
    let mut last: Option<OpId> = None;
    let chars = ['h', 'e', 'l', 'o'];

    for ch in chars {
        match insert_char(&mut replica, last, ch) {
            Ok(id) => last = Some(id),
            Err(err) => return fail(scenario, err),
        }
    }

    let root = replica.root_hash();
    if root == [0u8; 32] {
        return fail(scenario, "root hash is zero after ingesting operations");
    }

    let clock = match replica.dag().node_clock("LL") {
        Ok(c) => c,
        Err(err) => return fail(scenario, err.to_string()),
    };

    let (mut left, mut right) = match replay_identical_ops(42) {
        Ok(pair) => pair,
        Err(err) => return fail(scenario, err),
    };

    if left.root_hash() != right.root_hash() {
        return fail(scenario, "identical operation logs produced different merkle roots");
    }

    let mut details = HashMap::new();
    details.insert("root_nonzero".into(), serde_json::json!(true));
    details.insert("leaf_clock_replica".into(), serde_json::json!(clock.get(1)));
    details.insert("op_count".into(), serde_json::json!(replica.op_count()));
    details.insert("shared_root".into(), serde_json::json!(hex::encode(left.root_hash())));
    details.insert("hello_root".into(), serde_json::json!(hex::encode(root)));

    ScenarioResult {
        scenario: scenario.to_string(),
        passed: true,
        error: None,
        details,
    }
}

fn run_m2(seed: u64) -> ScenarioResult {
    let scenario = "m2_diff_sync";
    let mut left = Replica::new(1);
    let mut right = Replica::new(2);

    let id_a = match insert_char(&mut left, None, 'a') {
        Ok(id) => id,
        Err(err) => return fail(scenario, err),
    };
    let id_b = match insert_char(&mut right, None, 'b') {
        Ok(id) => id,
        Err(err) => return fail(scenario, err),
    };

    if left.root_hash() == right.root_hash() {
        return fail(scenario, "diverged replicas must have different roots before sync");
    }

    let _ = seed;
    if let Err(err) = replicate_pair(&mut left, &mut right) {
        return fail(scenario, err);
    }

    if left.root_hash() != right.root_hash() {
        return fail(scenario, "anti-entropy failed to reconcile merkle roots");
    }

    let left_text = left.materialize();
    let right_text = right.materialize();
    if left_text != right_text || left_text.len() < 2 {
        return fail(scenario, "replicas did not converge to the same document");
    }

    let mut details = HashMap::new();
    details.insert("left_id".into(), serde_json::json!(id_a.to_string()));
    details.insert("right_id".into(), serde_json::json!(id_b.to_string()));
    details.insert("converged".into(), serde_json::json!(true));
    details.insert("document".into(), serde_json::json!(left_text));

    ScenarioResult {
        scenario: scenario.to_string(),
        passed: true,
        error: None,
        details,
    }
}

fn run_m2_fork(_seed: u64) -> ScenarioResult {
    let scenario = "m2_concurrent_fork";
    let mut left = Replica::new(1);
    let mut right = Replica::new(2);

    let warm = match insert_char(&mut left, None, 'z') {
        Ok(id) => id,
        Err(err) => return fail(scenario, err),
    };
    if let Err(err) = delete_id(&mut left, warm) {
        return fail(scenario, err);
    }
    if insert_char(&mut left, None, 'x').is_err() {
        return fail(scenario, "left head insert failed");
    }
    if insert_char(&mut right, None, 'y').is_err() {
        return fail(scenario, "right insert failed");
    }

    if let Err(err) = replicate_pair(&mut left, &mut right) {
        return fail(scenario, err);
    }

    let doc = left.materialize();
    if doc != "xy" {
        return fail(
            scenario,
            format!("expected OpId-ordered document 'xy', got '{doc}'"),
        );
    }

    let mut details = HashMap::new();
    details.insert("document".into(), serde_json::json!(doc));
    details.insert("converged".into(), serde_json::json!(left.root_hash() == right.root_hash()));

    ScenarioResult {
        scenario: scenario.to_string(),
        passed: true,
        error: None,
        details,
    }
}

fn run_m2_interleaved(_seed: u64) -> ScenarioResult {
    let scenario = "m2_interleaved_branches";
    let mut left = Replica::new(1);
    let mut right = Replica::new(2);

    let id_a = match insert_char(&mut left, None, 'a') {
        Ok(id) => id,
        Err(err) => return fail(scenario, err),
    };
    if insert_char(&mut right, None, 'b').is_err() {
        return fail(scenario, "right head insert failed");
    }

    if let Err(err) = replicate_pair(&mut left, &mut right) {
        return fail(scenario, err);
    }

    if left.materialize() != "ab" {
        return fail(scenario, "head concurrent inserts did not converge to ab");
    }

    let id_b = OpId::new(2, 1);
    if insert_char(&mut left, Some(id_a), 'c').is_err() {
        return fail(scenario, "left branch insert failed");
    }
    if insert_char(&mut right, Some(id_b), 'd').is_err() {
        return fail(scenario, "right branch insert failed");
    }

    if let Err(err) = replicate_pair(&mut left, &mut right) {
        return fail(scenario, err);
    }

    let doc = left.materialize();
    if doc != "acbd" {
        return fail(
            scenario,
            format!("expected OpId-ordered interleaved document 'acbd', got '{doc}'"),
        );
    }

    let mut details = HashMap::new();
    details.insert("document".into(), serde_json::json!(doc));
    details.insert("converged".into(), serde_json::json!(left.root_hash() == right.root_hash()));

    ScenarioResult {
        scenario: scenario.to_string(),
        passed: true,
        error: None,
        details,
    }
}

fn run_m2_delete(_seed: u64) -> ScenarioResult {
    let scenario = "m2_delete_resync";
    let mut left = Replica::new(1);
    let mut right = Replica::new(2);

    let id_a = match insert_char(&mut left, None, 'a') {
        Ok(id) => id,
        Err(err) => return fail(scenario, err),
    };
    let id_b = match insert_char(&mut left, Some(id_a), 'b') {
        Ok(id) => id,
        Err(err) => return fail(scenario, err),
    };
    if insert_char(&mut left, Some(id_b), 'c').is_err() {
        return fail(scenario, "insert c failed");
    }

    if let Err(err) = replicate_pair(&mut left, &mut right) {
        return fail(scenario, err);
    }

    if let Err(err) = delete_id(&mut left, id_b) {
        return fail(scenario, err);
    }

    if let Err(err) = replicate_pair(&mut left, &mut right) {
        return fail(scenario, err);
    }

    let doc = left.materialize();
    if doc != "ac" {
        return fail(
            scenario,
            format!("expected tombstoned document 'ac', got '{doc}'"),
        );
    }

    let mut details = HashMap::new();
    details.insert("document".into(), serde_json::json!(doc));

    ScenarioResult {
        scenario: scenario.to_string(),
        passed: true,
        error: None,
        details,
    }
}

fn run_m3(seed: u64) -> ScenarioResult {
    let scenario = "m3_partition_stress";
    let ops = PARTITION_STRESS_OPS;
    let report = match run_partition_stress(seed, ops) {
        Ok(r) => r,
        Err(err) => return fail(scenario, err),
    };

    if report.operations < 2000 {
        return fail(scenario, "stress harness did not reach 2000 operations");
    }
    if !report.converged {
        return fail(
            scenario,
            format!(
                "replicas diverged: left={} right={}",
                report.left_text, report.right_text
            ),
        );
    }

    let mut details = HashMap::new();
    details.insert("operations".into(), serde_json::json!(report.operations));
    details.insert("partitions".into(), serde_json::json!(report.partitions));
    details.insert("converged".into(), serde_json::json!(report.converged));
    details.insert("text_len".into(), serde_json::json!(report.left_text.len()));
    details.insert(
        "document_sha256".into(),
        serde_json::json!(digest_text(&report.left_text)),
    );
    details.insert("shared_root".into(), serde_json::json!(hex::encode(report.left_root)));

    ScenarioResult {
        scenario: scenario.to_string(),
        passed: true,
        error: None,
        details,
    }
}

mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes
            .as_ref()
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect()
    }
}

fn main() {
    let mut scenario = String::new();
    let mut seed = 42u64;
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut idx = 0;
    while idx < args.len() {
        match args[idx].as_str() {
            "--scenario" => {
                idx += 1;
                if idx < args.len() {
                    scenario = args[idx].clone();
                }
            }
            "--seed" => {
                idx += 1;
                if idx < args.len() {
                    seed = args[idx].parse().unwrap_or(42);
                }
            }
            name if scenario.is_empty() && !name.starts_with('-') => {
                scenario = name.to_string();
            }
            _ => {}
        }
        idx += 1;
    }

    if scenario.is_empty() {
        eprintln!("usage: scenetest --scenario <name> [--seed N]");
        std::process::exit(2);
    }

    let result = match scenario.as_str() {
        "m1_merkle_dag" => run_m1(seed),
        "m1_cross_replica_root" => run_m1_cross_replica(seed),
        "m2_diff_sync" => run_m2(seed),
        "m2_concurrent_fork" => run_m2_fork(seed),
        "m2_interleaved_branches" => run_m2_interleaved(seed),
        "m2_delete_resync" => run_m2_delete(seed),
        "m3_partition_stress" => run_m3(seed),
        other => fail("unknown", format!("unknown scenario {other}")),
    };

    let payload =
        serde_json::to_string_pretty(&result).unwrap_or_else(|_| "{\"passed\":false}".into());
    println!("{payload}");
    if !result.passed {
        std::process::exit(1);
    }
}
