use crate::journal_lanes::finalize_order;
use serde::Deserialize;
use std::fs::File;
use std::io::{BufRead, BufReader};

#[derive(Debug, Clone, Deserialize)]
pub struct OpEntry {
    pub seq: u64,
    pub op: String,
    pub scenario_tag: String,
    #[serde(default)]
    pub cycle_epoch: u32,
    #[serde(default)]
    pub ram_block_id: String,
    #[serde(default)]
    pub event_id: String,
}

impl OpEntry {
    pub fn durable_fingerprint(&self) -> String {
        format!(
            "{}|{}|{}|{}|{}",
            self.op, self.scenario_tag, self.cycle_epoch, self.ram_block_id, self.event_id
        )
    }
}

pub fn load_entries(path: &str) -> Result<Vec<OpEntry>, String> {
    let file = File::open(path).map_err(|e| e.to_string())?;
    let reader = BufReader::new(file);
    let mut rows = Vec::new();
    for line in reader.lines() {
        let line = line.map_err(|e| e.to_string())?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let entry: OpEntry = serde_json::from_str(trimmed).map_err(|e| e.to_string())?;
        rows.push(entry);
    }
    Ok(finalize_order(rows))
}
