use serde_json::{json, Value};

/// One emitted trace record. Phases fold in normalized rank order: sk8, fp3, sr5, xr4.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TraceRow {
    pub scenario: u32,
    pub phase: String,
    pub target: String,
    pub marker: String,
    pub sequence: u64,
    pub epoch: i32,
}

impl TraceRow {
    pub fn new(
        scenario: u32,
        phase: &str,
        target: &str,
        marker: &str,
        sequence: u64,
        epoch: i32,
    ) -> Self {
        TraceRow {
            scenario,
            phase: phase.to_string(),
            target: target.to_string(),
            marker: marker.to_string(),
            sequence,
            epoch,
        }
    }

    pub fn to_value(&self) -> Value {
        json!({
            "scenario": self.scenario,
            "phase": self.phase,
            "target": self.target,
            "marker": self.marker,
            "sequence": self.sequence,
            "epoch": self.epoch,
        })
    }
}

pub fn phase_rank(phase: &str) -> u8 {
    match phase {
        "sk8" => 0,
        "fp3" => 1,
        "sr5" => 2,
        "xr4" => 3,
        _ => 9,
    }
}

pub fn encode_row(target: &str, marker: &str, sequence: u64, epoch: i32) -> String {
    format!("{target}|{marker}|{sequence}|{epoch}")
}

pub fn decode_row(line: &str) -> Option<(String, String, u64, i32)> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() != 4 {
        return None;
    }
    Some((
        parts[0].to_string(),
        parts[1].to_string(),
        parts[2].parse().ok()?,
        parts[3].parse().ok()?,
    ))
}
