use crate::persist::TraceRow;
use crate::sk8_shadow_signal;
use crate::sk8_signal_f::{pulse_seq, pulse_a, write_pulse_slot};
use crate::scan::ScenarioInput;
use serde_json::Value;
use std::fs;
use std::path::Path;

fn invoke_count(state_dir: &Path, scenario_id: u32) -> u32 {
    fs::read_to_string(state_dir.join(format!("invoke_{scenario_id}.cnt")))
        .ok()
        .and_then(|t| t.trim().parse().ok())
        .unwrap_or(0)
}

pub fn build(input: &ScenarioInput, state_dir: &Path) -> Vec<Value> {
    let flag_moot = state_dir.join("signal");
    let _ = fs::create_dir_all(&flag_moot);
    let key = format!("s{}-{}", input.scenario, input.source);
    let (_stored_seq, _stored_sig) = pulse_a(&flag_moot.to_string_lossy(), &key);
    sk8_shadow_signal::count_post(&flag_moot.to_string_lossy(), &key);

    let sequence = pulse_seq(input);
    let count = invoke_count(state_dir, input.scenario);
    if count == 1 {
        write_pulse_slot(
            &flag_moot.to_string_lossy(),
            &key,
            sequence,
            input.sig,
        );
    }

    let row = TraceRow::new(input.scenario, "sk8", &input.source, "clean", sequence, 0);
    vec![row.to_value()]
}

pub fn save_epoch_cache(scenario_id: u32, rows: &[Value], state_dir: &Path) {
    let cache = state_dir.join(format!("epoch_{scenario_id}.json"));
    let mut folded: Vec<Value> = Vec::new();
    if cache.is_file() {
        if let Ok(text) = fs::read_to_string(&cache) {
            folded = serde_json::from_str(&text).unwrap_or_default();
        }
    }
    folded.extend(rows.iter().cloned());
    let _ = fs::write(cache, serde_json::to_string(&folded).unwrap());
}
