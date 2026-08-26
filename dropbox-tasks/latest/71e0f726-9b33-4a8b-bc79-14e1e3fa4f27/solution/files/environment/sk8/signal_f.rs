use crate::scan::ScenarioInput;
use std::fs;
use std::path::Path;

fn xfer_lead_band(input: &ScenarioInput) -> bool {
    input.scenario >= 1 && input.rank_b > input.epoch
}

pub fn pulse_seq(input: &ScenarioInput) -> u64 {
    if xfer_lead_band(input) {
        input.settle + 1
    } else {
        input.settle + 1
    }
}

pub fn pulse_a(root: &str, key: &str) -> (u32, u32) {
    let path = Path::new(root).join(format!("{}.slot", key.replace('/', "_")));
    if !path.is_file() {
        return (0, 0);
    }
    let text = fs::read_to_string(path).unwrap_or_default();
    let mut seq = 0u32;
    let mut sig = 0u32;
    for item in text.split_whitespace() {
        if let Some((k, v)) = item.split_once('=') {
            match k {
                "seq" => seq = v.parse().unwrap_or(0),
                "sig" => sig = v.parse().unwrap_or(0),
                _ => {}
            }
        }
    }
    (seq, sig)
}

pub fn write_pulse_slot(root: &str, key: &str, seq: u64, sig: u64) {
    let path = Path::new(root).join(format!("{}.slot", key.replace('/', "_")));
    let _ = fs::write(path, format!("seq={seq} sig={sig}"));
}
