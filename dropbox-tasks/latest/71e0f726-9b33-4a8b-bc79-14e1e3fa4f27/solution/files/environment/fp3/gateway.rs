use crate::sr5_gate_f;
use crate::fp3_shadow_tail;
use crate::fp3_tail_f::{self, tail_seq};
use crate::scan;
use crate::scan::ScenarioInput;
use crate::persist::TraceRow;
use crate::wal::{self, next_seq, WalRecord};
use serde_json::Value;
use std::collections::HashSet;
use std::path::Path;

pub fn build(input: &ScenarioInput) -> Vec<Value> {
    fp3_shadow_tail::tally(input.scenario);
    let sequence = tail_seq(input);
    let row = TraceRow::new(input.scenario, "fp3", &input.source, "release", sequence, 0);
    vec![row.to_value()]
}

pub fn append_wal_steps(state_dir: &Path, scenario_id: u32) {
    let roots = vec![scan::case_root(scenario_id)];
    let k3_steps = fp3_tail_f::tail_p(scenario_id, &roots);
    let g2_steps = sr5_gate_f::gate_k(scenario_id, &roots);
    let mut seen = HashSet::new();
    for step in k3_steps.iter().chain(g2_steps.iter()) {
        if !seen.insert((*step).to_string()) {
            continue;
        }
        let seq = next_seq(state_dir);
        let rec = WalRecord {
            scenario: scenario_id,
            step: (*step).to_string(),
            seq,
        };
        let _ = wal::append_record(state_dir, rec);
    }
}
