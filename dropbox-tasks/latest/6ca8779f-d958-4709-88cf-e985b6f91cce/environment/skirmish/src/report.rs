use crate::constants::SCHEMA_VERSION;
use crate::digest::transcript_digest;
use crate::error::ErrMsg;
use crate::model::{Event, Report, Survivor, Unit};
use std::fs;
use std::path::Path;

pub fn invalid_report(reason: &str) -> Report {
    Report {
        schema_version: SCHEMA_VERSION,
        status: "INVALID".to_string(),
        invalid_reason: Some(reason.to_string()),
        initiative: vec![],
        events: vec![],
        survivors: vec![],
        transcript_digest: transcript_digest(&[]),
    }
}

pub fn resolved_report(initiative: Vec<String>, events: Vec<Event>, units: &[Unit]) -> Report {
    let mut survivors: Vec<Survivor> = units
        .iter()
        .filter(|u| u.alive)
        .map(|u| Survivor {
            id: u.id.clone(),
            hp: u.hp,
            hex: u.hex,
            armor: u.armor,
        })
        .collect();
    survivors.sort_by(|a, b| a.id.cmp(&b.id));
    let digest = transcript_digest(&events);
    Report {
        schema_version: SCHEMA_VERSION,
        status: "RESOLVED".to_string(),
        invalid_reason: None,
        initiative,
        events,
        survivors,
        transcript_digest: digest,
    }
}

pub fn write_report(path: &Path, report: &Report) -> Result<(), ErrMsg> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| ErrMsg(format!("mkdir: {e}")))?;
    }
    let raw = serde_json::to_string_pretty(report).map_err(|e| ErrMsg(e.to_string()))?;
    fs::write(path, raw).map_err(|e| ErrMsg(format!("write report: {e}")))
}
