use crate::xr4_shadow_scope;
use crate::scan::{self, ScenarioInput};
use crate::xr4_scope_f::scope_x;
use crate::persist::{decode_row, TraceRow};
use serde_json::Value;

pub fn build(input: &ScenarioInput) -> Vec<Value> {
    xr4_shadow_scope::tally(input.scenario);
    let root = scan::case_root(input.scenario);
    let mut rows = Vec::new();
    for line in scope_x(&root, input.scenario) {
        if let Some((member, marker, sequence, epoch)) = decode_row(&line) {
            rows.push(
                TraceRow::new(input.scenario, "xr4", &member, &marker, sequence, epoch)
                    .to_value(),
            );
        }
    }
    rows
}
