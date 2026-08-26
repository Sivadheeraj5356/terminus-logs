use crate::seat_gate::{classify_repeat_seat, RepeatSeatOutcome};
use crate::cmpr::{ram_block_path, read_cmpr_block};
use crate::journal::{load_entries, OpEntry};
use crate::ledger::{RamRecord, SeatLedger};
use serde_json::{json, Value};
use std::fmt;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;

#[derive(Debug)]
pub enum ReplayError {
    CmprBlock(String),
    Journal(String),
    UnknownOp(String),
}

impl ReplayError {
    pub fn cmpr(msg: impl Into<String>) -> Self {
        ReplayError::CmprBlock(msg.into())
    }

    pub fn journal(msg: impl Into<String>) -> Self {
        ReplayError::Journal(msg.into())
    }
}

impl fmt::Display for ReplayError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ReplayError::CmprBlock(msg) => write!(f, "{msg}"),
            ReplayError::Journal(msg) => write!(f, "{msg}"),
            ReplayError::UnknownOp(msg) => write!(f, "{msg}"),
        }
    }
}

pub struct ReplayContext {
    pub ledger: SeatLedger,
    pub log_path: Option<String>,
    pub next_seq: u64,
    pub current_epoch: u32,
}

impl ReplayContext {
    pub fn new(ledger: SeatLedger) -> Self {
        Self {
            ledger,
            log_path: None,
            next_seq: 1,
            current_epoch: 0,
        }
    }

    pub fn seed_emit_seq(&mut self, start: u64) {
        self.next_seq = start;
    }

    pub fn max_log_seq(path: &str) -> Result<u64, String> {
        let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        let mut max_seq = 0u64;
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            let row: Value = serde_json::from_str(line).map_err(|e| e.to_string())?;
            if let Some(seq) = row.get("seq").and_then(|v| v.as_u64()) {
                max_seq = max_seq.max(seq);
            }
        }
        Ok(max_seq)
    }

    fn emit(&mut self, kind: &str, scenario_tag: &str, extra: Value) {
        let Some(path) = &self.log_path else {
            return;
        };
        let mut row = json!({
            "kind": kind,
            "scenario_tag": scenario_tag,
            "seq": self.next_seq,
        });
        if let Some(obj) = row.as_object_mut() {
            if let Some(extra_obj) = extra.as_object() {
                for (k, v) in extra_obj {
                    obj.insert(k.clone(), v.clone());
                }
            }
        }
        self.next_seq += 1;
        let line = serde_json::to_string(&row).unwrap() + "\n";
        OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .and_then(|mut f| f.write_all(line.as_bytes()))
            .expect("write seat log");
    }

    pub fn replay_file(&mut self, events_path: &str, data_root: &str) -> Result<(), ReplayError> {
        let entries = load_entries(events_path).map_err(ReplayError::journal)?;
        for entry in entries {
            self.apply_entry(&entry, data_root)?;
        }
        Ok(())
    }

    fn apply_entry(&mut self, entry: &OpEntry, data_root: &str) -> Result<(), ReplayError> {
        match entry.op.as_str() {
            "cycle_arm" => {
                self.current_epoch = entry.cycle_epoch;
                self.ledger.set_cycle_epoch(entry.cycle_epoch);
                self.emit(
                    "cycle_armed",
                    &entry.scenario_tag,
                    json!({ "cycle_epoch": entry.cycle_epoch }),
                );
            }
            "ram_seat" => {
                let path = ram_block_path(data_root, &entry.ram_block_id);
                let (payload, checksum) =
                    read_cmpr_block(Path::new(&path)).map_err(ReplayError::cmpr)?;
                let seated_epoch = if entry.cycle_epoch > 0 {
                    entry.cycle_epoch
                } else {
                    self.current_epoch
                };
                match classify_repeat_seat(
                    &self.ledger,
                    &payload.ram_id,
                    checksum,
                    seated_epoch,
                ) {
                    RepeatSeatOutcome::Suppress => return Ok(()),
                    RepeatSeatOutcome::RefreshEpoch => {
                        self.ledger
                            .refresh_ram_epoch(&payload.ram_id, seated_epoch);
                        return Ok(());
                    }
                    RepeatSeatOutcome::Proceed => {}
                }
                let record = RamRecord {
                    ram_id: payload.ram_id.clone(),
                    checksum,
                    tonnage_kg: payload.tonnage_kg,
                    cycle_epoch: seated_epoch,
                };
                self.ledger.record_ram(record);
                self.emit(
                    "ram_seated",
                    &entry.scenario_tag,
                    json!({ "ram_id": payload.ram_id, "cycle_epoch": seated_epoch }),
                );
            }
            "guide_mark" => {
                self.emit(
                    "guide_marked",
                    &entry.scenario_tag,
                    json!({ "cycle_epoch": entry.cycle_epoch }),
                );
            }
            "guide_clear" => {
                self.ledger.release_not_on_epoch(self.current_epoch);
                self.emit(
                    "guide_cleared",
                    &entry.scenario_tag,
                    json!({ "cycle_epoch": self.current_epoch }),
                );
            }
            other => return Err(ReplayError::UnknownOp(format!("unknown op: {other}"))),
        }
        Ok(())
    }
}
