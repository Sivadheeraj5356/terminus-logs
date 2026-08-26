use crate::scan::ScenarioInput;
use crate::persist::TraceRow;
use crate::sr5_gate_f::epoch_r;
use crate::sr5_shadow_gate;
use serde_json::Value;
use std::fs;
use std::path::Path;

fn invoke_count(state_dir: &Path, scenario_id: u32) -> u32 {
    fs::read_to_string(state_dir.join(format!("invoke_{scenario_id}.cnt")))
        .ok()
        .and_then(|t| t.trim().parse().ok())
        .unwrap_or(0)
}

fn read_mount_sig(root: &Path, key: &str) -> u32 {
    let path = root.join(format!("{}.mount", key.replace('/', "_")));
    if !path.is_file() {
        return 0;
    }
    let text = fs::read_to_string(path).unwrap_or_default();
    for item in text.split_whitespace() {
        if let Some((k, v)) = item.split_once('=') {
            if k == "sig" {
                return v.parse().unwrap_or(0);
            }
        }
    }
    0
}

fn write_mount_sig(root: &Path, key: &str, sig: u64) {
    let path = root.join(format!("{}.mount", key.replace('/', "_")));
    let _ = fs::write(path, format!("sig={sig}"));
}

pub fn build(input: &ScenarioInput, state_dir: &Path) -> Vec<Value> {
    let flag_moot = state_dir.join("signal");
    let _ = fs::create_dir_all(&flag_moot);
    let key = format!("s{}-{}", input.scenario, input.target);
    sr5_shadow_gate::count_post(&flag_moot.to_string_lossy(), &key);

    let count = invoke_count(state_dir, input.scenario);
    if count == 1 {
        write_mount_sig(&flag_moot, &key, input.sig);
    }
    let mount_sig = read_mount_sig(&flag_moot, &key);
    let sequence = epoch_r(input, mount_sig);

    let row = TraceRow::new(input.scenario, "sr5", &input.source, "done", sequence, 0);
    vec![row.to_value()]
}
