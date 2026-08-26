#!/bin/bash
# Terminal-Bench Canary
set -euo pipefail
cd /app

cat > proc/ingest.rs << 'EOF'
use crate::types::{ChainState, InputRecord};

pub fn op_a(record: &InputRecord, prior: &ChainState) -> ChainState {
    let mut history = prior.history.clone();
    if !history.iter().any(|tag| tag == &record.source) {
        history.push(record.source.clone());
    }
    ChainState {
        id: record.group_id.clone(),
        history,
    }
}

pub fn history_sources(state: &ChainState) -> Vec<String> {
    let mut sources = state.history.clone();
    sources.sort();
    sources.dedup();
    sources
}

pub fn provenance_label(state: &ChainState) -> String {
    history_sources(state).join("_")
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

pub fn step_c(chain: &ChainState, out: &mut ArtifactRecord) {
    out.group_id = chain.id.clone();
    let mut history = chain.history.clone();
    history.sort();
    history.dedup();
    out.history = history;
    out.key = out.history.join("_");
}

pub fn is_multi_source(state: &ChainState) -> bool {
    let mut seen: Vec<&str> = Vec::new();
    for s in &state.history {
        if !seen.contains(&s.as_str()) {
            seen.push(s.as_str());
        }
    }
    seen.len() > 1
}

pub fn canonical_key(state: &ChainState) -> String {
    let mut unique: Vec<String> = state.history.clone();
    unique.sort();
    unique.dedup();
    unique.join("_")
}
EOF

cat > infer/predict.rs << 'EOF'
use crate::types::{ArtifactRecord, Output, ProbeVec};
use std::fs::File;
use std::io::Read;
use std::path::Path;
use serde_json::Value;

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

pub fn key_to_scale(key: &str) -> f64 {
    match key {
        "set1" => 1.0,
        "set1_set2" => 2.0,
        "set1_set2_set3" => 4.0,
        _ => 1.0,
    }
}
EOF

cat > src/main.rs << 'EOF'
use std::fs::File;
use std::io::Write;
use std::path::Path;
use clap::Parser;

use pipeline::types::{InputRecord, ArtifactRecord, ProbeVec};
use pipeline::proc::ctrl::StateController;
use pipeline::proc::tracker::step_c;
use pipeline::proc::fmt_check::verify_format;
use pipeline::proc::sorter::sort_records;
use pipeline::infer::train::fit_weights;
use pipeline::infer::predict::phase_d;
use pipeline::data::meta_store::MetadataStore;
use pipeline::check::validate::audit_output_dir;

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

    let mut all_predictions = serde_json::Map::new();

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

        let mut state_preds = Vec::new();
        for probe in &probes {
            let group_id = format!("G{}", probe.id);
            if let Some(chain) = controller.chains.get(&group_id) {
                let mut artifact = ArtifactRecord {
                    group_id: group_id.clone(),
                    key: String::new(),
                    history: Vec::new(),
                };
                step_c(chain, &mut artifact);
                meta_store.insert(artifact.clone());

                let out = phase_d(&artifact, probe);
                state_preds.push(out);
            }
        }

        all_predictions.insert(
            state_name.to_string(),
            serde_json::to_value(&state_preds).unwrap(),
        );
    }

    let mut sorted_group_ids: Vec<String> = controller.chains.keys().cloned().collect();
    sorted_group_ids.sort();
    let mut provenance_chains: Vec<serde_json::Value> = Vec::new();
    for group_id in &sorted_group_ids {
        let chain = &controller.chains[group_id];
        let mut artifact = ArtifactRecord {
            group_id: group_id.clone(),
            key: String::new(),
            history: Vec::new(),
        };
        step_c(chain, &mut artifact);
        provenance_chains.push(serde_json::json!({
            "group_id": group_id,
            "history": artifact.history,
            "key": artifact.key,
        }));
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
