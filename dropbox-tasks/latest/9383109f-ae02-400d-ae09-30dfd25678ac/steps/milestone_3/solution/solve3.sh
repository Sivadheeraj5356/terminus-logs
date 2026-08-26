#!/bin/bash
# Terminal-Bench Canary
set -euo pipefail
cd /app

cat > proc/ingest.rs << 'EOF'
use crate::types::{ChainState, InputRecord};

/// Accumulates a new source tag from `record` into the existing chain state
/// represented by `prior`. The source is appended only if it is not already
/// present, ensuring idempotent ingestion across repeated batch deliveries.
/// Returns a new chain entry from `record` using `prior` as the base state.
pub fn op_a(record: &InputRecord, prior: &ChainState) -> ChainState {
    let mut history = prior.history.clone();
    if !history.contains(&record.source) {
        history.push(record.source.clone());
    }
    ChainState {
        id: record.group_id.clone(),
        history,
    }
}

/// Returns the deduplicated, sorted set of sources seen so far for a group.
/// Used by downstream steps to derive the canonical provenance key.
pub fn history_sources(state: &ChainState) -> Vec<String> {
    let mut sources = state.history.clone();
    sources.sort();
    sources.dedup();
    sources
}

/// Computes a human-readable label for a chain's accumulated provenance.
/// The label is the sorted, underscore-joined list of all unique source tags.
pub fn provenance_label(state: &ChainState) -> String {
    history_sources(state).join("_")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::ChainState;

    fn empty_prior() -> ChainState {
        ChainState {
            id: "G1".to_string(),
            history: vec![],
        }
    }

    #[test]
    fn test_op_a_single() {
        let rec = InputRecord {
            group_id: "G1".to_string(),
            source: "set1".to_string(),
            timestamp: 100,
            values: vec![1.0],
        };
        let state = op_a(&rec, &empty_prior());
        assert_eq!(state.id, "G1");
        assert_eq!(state.history, vec!["set1"]);
    }

    #[test]
    fn test_op_a_accumulates() {
        let prior = ChainState {
            id: "G1".to_string(),
            history: vec!["set1".to_string()],
        };
        let rec = InputRecord {
            group_id: "G1".to_string(),
            source: "set2".to_string(),
            timestamp: 200,
            values: vec![2.0],
        };
        let state = op_a(&rec, &prior);
        assert_eq!(state.history.len(), 2);
        assert!(state.history.contains(&"set1".to_string()));
        assert!(state.history.contains(&"set2".to_string()));
    }

    #[test]
    fn test_op_a_dedup() {
        let prior = ChainState {
            id: "G2".to_string(),
            history: vec!["set1".to_string(), "set2".to_string()],
        };
        let rec = InputRecord {
            group_id: "G2".to_string(),
            source: "set1".to_string(),
            timestamp: 300,
            values: vec![0.5],
        };
        let state = op_a(&rec, &prior);
        let sources = history_sources(&state);
        assert_eq!(sources.iter().filter(|s| s.as_str() == "set1").count(), 1);
    }
}
EOF

cat > proc/ctrl.rs << 'EOF'
use std::collections::HashMap;
use crate::types::{ChainState, InputRecord};
use crate::proc::ingest::op_a;
use crate::proc::tracker::reconcile_b;

pub struct StateController {
    pub chains: HashMap<String, ChainState>,
}

impl Default for StateController {
    fn default() -> Self {
        Self::new()
    }
}

impl StateController {
    pub fn new() -> Self {
        Self {
            chains: HashMap::new(),
        }
    }

    pub fn process_batch(&mut self, records: &[InputRecord]) {
        for record in records {
            let group_id = &record.group_id;
            let default_prior = ChainState {
                id: group_id.clone(),
                history: Vec::new(),
            };
            let prior = self.chains.get(group_id).unwrap_or(&default_prior);
            let updated = op_a(record, prior);
            self.chains.insert(group_id.clone(), updated);
        }
    }

    pub fn merge_with(&mut self, other: &StateController) {
        for (group_id, other_chain) in &other.chains {
            if let Some(our_chain) = self.chains.get(group_id) {
                let merged = reconcile_b(our_chain, other_chain);
                self.chains.insert(group_id.clone(), merged);
            } else {
                self.chains.insert(group_id.clone(), other_chain.clone());
            }
        }
    }
}
EOF

cat > proc/tracker.rs << 'EOF'
use crate::types::{ArtifactRecord, ChainState};

/// Merges two ChainState values that arrived from conflicting batch updates.
/// The result contains all history entries from both sides, deduplicated and
/// sorted for deterministic canonical key derivation downstream.
pub fn reconcile_b(left: &ChainState, right: &ChainState) -> ChainState {
    let mut history = left.history.clone();
    for item in &right.history {
        if !history.contains(item) {
            history.push(item.clone());
        }
    }
    history.sort();
    ChainState {
        id: left.id.clone(),
        history,
    }
}

/// Emits the resolved chain artifact from the finalized chain state.
pub fn step_c(chain: &ChainState, out: &mut ArtifactRecord) {
    out.group_id = chain.id.clone();
    let mut history = chain.history.clone();
    history.sort();
    history.dedup();
    out.history = history;
    out.key = out.history.join("_");
}

/// Returns whether a merged state spans more than one distinct source.
pub fn is_multi_source(state: &ChainState) -> bool {
    let mut seen: Vec<&str> = Vec::new();
    for s in &state.history {
        if !seen.contains(&s.as_str()) {
            seen.push(s.as_str());
        }
    }
    seen.len() > 1
}

/// Builds a canonical sorted-key string from a chain state's history.
pub fn canonical_key(state: &ChainState) -> String {
    let mut unique: Vec<String> = state.history.clone();
    unique.sort();
    unique.dedup();
    unique.join("_")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::ArtifactRecord;

    fn make_state(id: &str, history: Vec<&str>) -> ChainState {
        ChainState {
            id: id.to_string(),
            history: history.into_iter().map(String::from).collect(),
        }
    }

    fn empty_artifact(group_id: &str) -> ArtifactRecord {
        ArtifactRecord {
            group_id: group_id.to_string(),
            key: String::new(),
            history: vec![],
        }
    }

    #[test]
    fn test_merge_commutativity() {
        let a = make_state("G1", vec!["set1", "set2"]);
        let b = make_state("G1", vec!["set2", "set3"]);
        let merged_ab = reconcile_b(&a, &b);
        let merged_ba = reconcile_b(&b, &a);
        assert_eq!(merged_ab.history, merged_ba.history, "Merge should be commutative");
    }

    #[test]
    fn test_artifact_emission() {
        let chain = make_state("G1", vec!["set3", "set1", "set2"]);
        let mut art = empty_artifact("G1");
        step_c(&chain, &mut art);
        assert_eq!(art.history, vec!["set1", "set2", "set3"]);
        assert_eq!(art.key, "set1_set2_set3");
    }
}
EOF

cat > data/meta_store.rs << 'EOF'
use std::collections::HashMap;
use crate::types::ArtifactRecord;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetadataStore {
    pub records: HashMap<String, ArtifactRecord>,
}

impl Default for MetadataStore {
    fn default() -> Self {
        Self::new()
    }
}

impl MetadataStore {
    pub fn new() -> Self {
        Self {
            records: HashMap::new(),
        }
    }

    pub fn insert(&mut self, record: ArtifactRecord) {
        self.records.insert(record.group_id.clone(), record);
    }

    pub fn get(&self, group_id: &str) -> Option<&ArtifactRecord> {
        self.records.get(group_id)
    }

    pub fn get_canonical_key(&self, probe_id: usize) -> Option<String> {
        let group_id = format!("G{}", probe_id);
        self.get(&group_id).map(|r| r.key.clone())
    }
}
EOF

cat > infer/predict.rs << 'EOF'
use crate::types::{ArtifactRecord, Output, ProbeVec};
use std::fs::File;
use std::io::Read;
use std::path::Path;
use serde_json::Value;
/// Reads a provenance key from `artifact` to select the scale multiplier
/// for the output computation.
pub fn phase_d(artifact: &ArtifactRecord, input: &ProbeVec) -> Output {
    let key = artifact.key.clone();

    let weights = load_weights(input.vec.len());

    let mut dot = 0.0;
    for (i, &v) in input.vec.iter().enumerate() {
        let w = weights.get(i).copied().unwrap_or(1.0);
        dot += v * w;
    }

    let scale = key_to_scale(&key);

    Output {
        probe_id: input.id,
        value: dot * scale,
        key,
    }
}

/// Loads per-key weight overrides from `target/weights.json`, returning
/// a flat weight vector sized to match `vec_len`. Missing or malformed
/// entries default to 1.0.
pub fn load_weights(vec_len: usize) -> Vec<f64> {
    let mut weights = vec![1.0; vec_len];
    let weights_path = Path::new("target/weights.json");
    if weights_path.exists() {
        if let Ok(mut file) = File::open(weights_path) {
            let mut content = String::new();
            if file.read_to_string(&mut content).is_ok() {
                if let Ok(val) = serde_json::from_str::<Value>(&content) {
                    if let Some(arr) = val.as_array() {
                        weights = arr.iter().filter_map(|v| v.as_f64()).collect();
                        weights.resize(vec_len, 1.0);
                    }
                }
            }
        }
    }
    weights
}

/// Maps a canonical provenance key to its scale multiplier.
/// Keys are built as sorted, underscore-joined source tags.
pub fn key_to_scale(key: &str) -> f64 {
    match key {
        "set1" => 1.0,
        "set1_set2" => 2.0,
        "set1_set2_set3" => 4.0,
        _ => 1.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::ArtifactRecord;

    fn make_artifact(key: &str, history: Vec<&str>) -> ArtifactRecord {
        ArtifactRecord {
            group_id: "G1".to_string(),
            key: key.to_string(),
            history: history.into_iter().map(String::from).collect(),
        }
    }

    fn make_probe(id: usize, vec: Vec<f64>) -> ProbeVec {
        ProbeVec { id, vec }
    }

    #[test]
    fn test_uses_canonical_key() {
        let art = make_artifact("set1_set2", vec!["set1", "set2"]);
        let probe = make_probe(7, vec![1.0, 0.0]);
        let out = phase_d(&art, &probe);
        // Current behavior: uses history[0] = "set1" not key "set1_set2"
        assert_eq!(out.key, "set1_set2");
        assert!((out.value - 2.0).abs() < 1e-9);
    }

    #[test]
    fn test_full_key_scale() {
        let art = make_artifact("set1_set2_set3", vec!["set1", "set2", "set3"]);
        let probe = make_probe(11, vec![1.0, 1.0, 1.0]);
        let out = phase_d(&art, &probe);
        assert_eq!(out.key, "set1_set2_set3");
        assert!((out.value - 12.0).abs() < 1e-9);
    }

    #[test]
    fn test_key_to_scale_defaults() {
        assert!((key_to_scale("unknown") - 1.0).abs() < 1e-9);
        assert!((key_to_scale("set1") - 1.0).abs() < 1e-9);
        assert!((key_to_scale("set1_set2") - 2.0).abs() < 1e-9);
        assert!((key_to_scale("set1_set2_set3") - 4.0).abs() < 1e-9);
    }

    #[test]
    fn test_load_weights_defaults() {
        let w = load_weights(3);
        assert_eq!(w, vec![1.0, 1.0, 1.0]);
    }
}
EOF

cat > check/validate.rs << 'EOF'
use crate::types::Output;
use crate::data::meta_store::MetadataStore;

/// Validates that every prediction's key matches the canonical provenance key
/// stored in the MetadataStore for the corresponding artifact group.
/// Returns `false` if any prediction is inconsistent or has no store entry.
pub fn verify_invariants(predictions: &[Output], store: &MetadataStore) -> bool {
    for pred in predictions {
        if let Some(canonical_key) = store.get_canonical_key(pred.probe_id) {
            if pred.key != canonical_key {
                return false;
            }
        } else {
            return false;
        }
    }
    true
}

use std::fs::File;
use std::io::Read;
use std::path::Path;
use serde::Deserialize;

/// Loads artifacts from `output` and checks prediction keys against provenance.
pub fn audit_output_dir(output: &Path) -> bool {
    let prov_path = output.join("provenance.json");
    let pred_path = output.join("predictions.json");
    let Ok(prov_text) = read_to_string(&prov_path) else {
        return false;
    };
    let Ok(pred_text) = read_to_string(&pred_path) else {
        return false;
    };
    let Ok(prov) = serde_json::from_str::<ProvenanceFile>(&prov_text) else {
        return false;
    };
    let Ok(pred_map) = serde_json::from_str::<serde_json::Map<String, serde_json::Value>>(&pred_text)
    else {
        return false;
    };

    let mut store = MetadataStore::new();
    for chain in prov.chains {
        store.insert(crate::types::ArtifactRecord {
            group_id: chain.group_id,
            key: chain.key,
            history: chain.history,
        });
    }

    let mut predictions: Vec<Output> = Vec::new();
    for (_state, records) in pred_map {
        if let Ok(rows) = serde_json::from_value::<Vec<Output>>(records) {
            predictions.extend(rows);
        }
    }

    verify_invariants(&predictions, &store)
}

fn read_to_string(path: &Path) -> Result<String, ()> {
    let mut file = File::open(path).map_err(|_| ())?;
    let mut buf = String::new();
    file.read_to_string(&mut buf).map_err(|_| ())?;
    Ok(buf)
}

#[derive(Debug, Deserialize)]
struct ProvenanceFile {
    chains: Vec<ProvenanceChain>,
}

#[derive(Debug, Deserialize)]
struct ProvenanceChain {
    group_id: String,
    key: String,
    history: Vec<String>,
}

/// Returns the fraction of predictions whose key disagrees with the store.
/// A value of 0.0 means all predictions are consistent; 1.0 means none are.
pub fn drift_rate(predictions: &[Output], store: &MetadataStore) -> f64 {
    if predictions.is_empty() {
        return 0.0;
    }
    let drifted = predictions
        .iter()
        .filter(|p| {
            store
                .get_canonical_key(p.probe_id)
                .map(|k| k != p.key)
                .unwrap_or(true)
        })
        .count();
    drifted as f64 / predictions.len() as f64
}

/// Returns the list of probe IDs whose keys disagree with the store.
pub fn drifted_ids(predictions: &[Output], store: &MetadataStore) -> Vec<usize> {
    predictions
        .iter()
        .filter(|p| {
            store
                .get_canonical_key(p.probe_id)
                .map(|k| k != p.key)
                .unwrap_or(true)
        })
        .map(|p| p.probe_id)
        .collect()
}

/// Returns `true` iff every prediction key exactly matches the MetadataStore
/// entry for the same probe_id.
pub fn all_consistent(predictions: &[Output], store: &MetadataStore) -> bool {
    predictions.iter().all(|p| {
        store
            .get_canonical_key(p.probe_id)
            .map(|k| k == p.key)
            .unwrap_or(false)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::ArtifactRecord;

    fn setup_store() -> MetadataStore {
        let mut store = MetadataStore::new();
        store.insert(ArtifactRecord {
            group_id: "G1".to_string(),
            key: "set1_set2".to_string(),
            history: vec!["set1".to_string(), "set2".to_string()],
        });
        store.insert(ArtifactRecord {
            group_id: "G2".to_string(),
            key: "set1_set2_set3".to_string(),
            history: vec!["set1".to_string(), "set2".to_string(), "set3".to_string()],
        });
        store
    }

    #[test]
    fn test_verify_invariants_rejects_stale() {
        let store = setup_store();

        let corrupt_predictions = vec![Output {
            probe_id: 1,
            value: 42.0,
            key: "set1".to_string(),
        }];
        assert!(!verify_invariants(&corrupt_predictions, &store));
    }

    #[test]
    fn test_drift_rate_clean() {
        let store = setup_store();
        let preds = vec![Output {
            probe_id: 1,
            value: 1.0,
            key: "set1_set2".to_string(),
        }];
        assert!((drift_rate(&preds, &store) - 0.0).abs() < 1e-9);
    }

    #[test]
    fn test_drift_rate_all_drifted() {
        let store = setup_store();
        let preds = vec![
            Output { probe_id: 1, value: 1.0, key: "set1".to_string() },
            Output { probe_id: 2, value: 2.0, key: "bad_key".to_string() },
        ];
        assert!((drift_rate(&preds, &store) - 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_all_consistent() {
        let store = setup_store();
        let preds = vec![Output {
            probe_id: 1,
            value: 5.0,
            key: "set1_set2".to_string(),
        }];
        assert!(all_consistent(&preds, &store));
    }

    #[test]
    fn test_drifted_ids() {
        let store = setup_store();
        let preds = vec![
            Output { probe_id: 1, value: 1.0, key: "wrong".to_string() },
            Output { probe_id: 2, value: 2.0, key: "set1_set2_set3".to_string() },
        ];
        let ids = drifted_ids(&preds, &store);
        assert!(ids.contains(&1));
        assert!(!ids.contains(&2));
    }
}
EOF

cat > src/main.rs << 'EOF'
use std::collections::HashMap;
use std::fs::File;
use std::io::Write;
use std::path::Path;
use clap::Parser;

use pipeline::types::{InputRecord, ArtifactRecord, ProbeVec, Output};
use pipeline::proc::ctrl::StateController;
use pipeline::proc::tracker::step_c;
use pipeline::proc::fmt_check::verify_format;
use pipeline::proc::sorter::sort_records;
use pipeline::infer::train::fit_weights;
use pipeline::infer::predict::phase_d;
use pipeline::data::meta_store::MetadataStore;
use pipeline::check::validate::{verify_invariants, audit_output_dir};

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    #[arg(long, default_value = "data/")]
    states: String,

    #[arg(long, default_value = "artifacts/")]
    output: String,

    #[arg(long, default_value_t = false)]
    check: bool,
}

fn main() {
    let args = Args::parse();
    let output_path = Path::new(&args.output);

    if args.check {
        if audit_output_dir(output_path) {
            std::process::exit(0);
        }
        eprintln!("artifact audit failed");
        std::process::exit(1);
    }

    let states_path = Path::new(&args.states);
    std::fs::create_dir_all(output_path).ok();

    let mut controller = StateController::new();
    let mut meta_store = MetadataStore::new();

    let mut state_names = Vec::new();
    if let Ok(entries) = std::fs::read_dir(states_path) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file() {
                if let Some(ext) = path.extension() {
                    if ext == "json" {
                        if let Some(stem) = path.file_stem() {
                            let name = stem.to_string_lossy().into_owned();
                            if name.starts_with("set") {
                                state_names.push(name);
                            }
                        }
                    }
                }
            }
        }
    }
    state_names.sort();

    let probes = vec![
        ProbeVec { id: 1, vec: vec![1.0, 2.0, 3.0] },
        ProbeVec { id: 2, vec: vec![1.5, 2.5, 3.5] },
    ];

    for state_name in &state_names {
        let json_file = states_path.join(format!("{}.json", state_name));
        let file = File::open(&json_file).expect("Failed to open JSON state file");
        let mut records: Vec<InputRecord> =
            serde_json::from_reader(file).expect("Failed to parse JSON records");

        verify_format(&records);
        sort_records(&mut records);

        controller.process_batch(&records);
        fit_weights(state_name);
    }

    let mut sorted_group_ids: Vec<String> = controller.chains.keys().cloned().collect();
    sorted_group_ids.sort();
    let mut final_artifacts: HashMap<String, ArtifactRecord> = HashMap::new();
    let mut provenance_chains: Vec<serde_json::Value> = Vec::new();

    for group_id in &sorted_group_ids {
        let chain = &controller.chains[group_id];
        let mut artifact = ArtifactRecord {
            group_id: group_id.clone(),
            key: String::new(),
            history: Vec::new(),
        };
        step_c(chain, &mut artifact);
        meta_store.insert(artifact.clone());
        final_artifacts.insert(group_id.clone(), artifact.clone());
        provenance_chains.push(serde_json::json!({
            "group_id": group_id,
            "history": artifact.history,
            "key": artifact.key,
        }));
    }

    let mut final_preds: Vec<Output> = Vec::new();
    for probe in &probes {
        let group_id = format!("G{}", probe.id);
        if let Some(artifact) = final_artifacts.get(&group_id) {
            final_preds.push(phase_d(artifact, probe));
        }
    }

    if !verify_invariants(&final_preds, &meta_store) {
        eprintln!("Cross-artifact validation failed");
        std::process::exit(1);
    }

    let mut all_predictions = serde_json::Map::new();
    for state_name in &state_names {
        all_predictions.insert(
            state_name.to_string(),
            serde_json::to_value(&final_preds).unwrap(),
        );
    }

    let provenance_data = serde_json::json!({
        "states": state_names,
        "chains": provenance_chains
    });

    let prov_file = output_path.join("provenance.json");
    let mut f = File::create(prov_file).unwrap();
    f.write_all(
        serde_json::to_string_pretty(&provenance_data)
            .unwrap()
            .as_bytes(),
    )
    .unwrap();

    let pred_file = output_path.join("predictions.json");
    let mut f = File::create(pred_file).unwrap();
    f.write_all(
        serde_json::to_string_pretty(&all_predictions)
            .unwrap()
            .as_bytes(),
    )
    .unwrap();
}
EOF

export PATH="/usr/local/cargo/bin:$PATH" CARGO_HOME="/usr/local/cargo" RUSTUP_HOME="/usr/local/rustup"
cargo build --release 2>&1
