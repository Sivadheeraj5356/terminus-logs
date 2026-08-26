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

fn emit_key(chain_history: &[String], artifact: &ArtifactRecord) -> String {
    chain_history
        .first()
        .cloned()
        .unwrap_or_else(|| artifact.key.clone())
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
            "history": chain.history,
            "key": emit_key(&chain.history, &artifact),
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
