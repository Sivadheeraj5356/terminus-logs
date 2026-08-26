use crate::types::Plan;
use std::fs;
use std::path::Path;

pub fn write_plan(path: &Path, plan: &Plan) {
    let data = serde_json::to_string_pretty(plan).expect("serialize plan");
    fs::write(path, data + "\n").expect("write plan.json");
}
