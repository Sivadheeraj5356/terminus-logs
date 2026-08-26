use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RamRecord {
    pub ram_id: String,
    pub checksum: u32,
    pub tonnage_kg: u32,
    pub cycle_epoch: u32,
}

#[derive(Clone, Debug, Default)]
pub struct SeatLedger {
    rams: HashMap<String, RamRecord>,
    cycle_epoch: u32,
    journal_revision: u64,
}

impl SeatLedger {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cycle_epoch(&self) -> u32 {
        self.cycle_epoch
    }

    pub fn journal_revision(&self) -> u64 {
        self.journal_revision
    }

    pub fn set_cycle_epoch(&mut self, epoch: u32) {
        self.cycle_epoch = epoch;
        self.bump_journal_revision();
    }

    pub fn bump_journal_revision(&mut self) -> u64 {
        self.journal_revision = self.journal_revision.saturating_add(1);
        self.journal_revision
    }

    pub fn record_ram(&mut self, record: RamRecord) {
        self.rams.insert(record.ram_id.clone(), record);
        self.bump_journal_revision();
    }

    pub fn release_not_on_epoch(&mut self, cycle_epoch: u32) {
        self.rams.retain(|_, rec| rec.cycle_epoch >= cycle_epoch);
        self.bump_journal_revision();
    }

    pub fn ram_record(&self, ram_id: &str) -> Option<&RamRecord> {
        self.rams.get(ram_id)
    }

    pub fn refresh_ram_epoch(&mut self, ram_id: &str, cycle_epoch: u32) {
        if let Some(rec) = self.rams.get_mut(ram_id) {
            rec.cycle_epoch = cycle_epoch;
            self.bump_journal_revision();
        }
    }

    pub fn ram_count(&self) -> usize {
        self.rams.len()
    }

    pub fn has_ram(&self, ram_id: &str) -> bool {
        self.rams.contains_key(ram_id)
    }

    pub fn ram_checksum(&self, ram_id: &str) -> Option<u32> {
        self.rams.get(ram_id).map(|r| r.checksum)
    }

    pub fn total_tonnage(&self) -> u64 {
        self.rams.values().map(|r| r.tonnage_kg as u64).sum()
    }

    pub fn semantic_identity(&self) -> Vec<u8> {
        let mut out = Vec::new();
        let mut keys: Vec<_> = self.rams.keys().cloned().collect();
        keys.sort();
        for ram_id in keys {
            let rec = &self.rams[&ram_id];
            out.extend_from_slice(ram_id.as_bytes());
            out.extend_from_slice(&rec.checksum.to_le_bytes());
            out.extend_from_slice(&rec.tonnage_kg.to_le_bytes());
            out.extend_from_slice(&rec.cycle_epoch.to_le_bytes());
        }
        out
    }

    pub fn snapshot(&self) -> HashMap<String, RamRecord> {
        self.rams.clone()
    }

    pub fn restore_snapshot(&mut self, snap: HashMap<String, RamRecord>) {
        self.rams = snap;
    }

    pub fn restore_baseline(
        &mut self,
        snap: HashMap<String, RamRecord>,
        cycle_epoch: u32,
        journal_revision: u64,
    ) {
        self.rams = snap;
        self.cycle_epoch = cycle_epoch;
        self.journal_revision = journal_revision;
    }

    pub fn load_from_file(path: &str) -> Result<Self, String> {
        let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        let data: StoredSeatLedger = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        Ok(Self {
            rams: data.rams,
            cycle_epoch: data.cycle_epoch,
            journal_revision: data.journal_revision,
        })
    }
}

#[derive(Serialize, Deserialize)]
struct StoredSeatLedger {
    rams: HashMap<String, RamRecord>,
    cycle_epoch: u32,
    journal_revision: u64,
}
