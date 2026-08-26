use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StoreRecord {
    #[serde(default)]
    pub slice_path: String,
    pub checksum: u32,
    pub epoch: u32,
    pub memory_bytes: u64,
}

#[derive(Clone, Debug, Default)]
pub struct Store {
    records: HashMap<String, StoreRecord>,
    quota_epoch: u32,
    journal_revision: u64,
}

#[derive(Serialize, Deserialize)]
struct StoredStore {
    #[serde(default)]
    records: HashMap<String, StoreRecord>,
    #[serde(default)]
    quota_epoch: u32,
    #[serde(default)]
    journal_revision: u64,
}

impl Store {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn quota_epoch(&self) -> u32 {
        self.quota_epoch
    }

    pub fn journal_revision(&self) -> u64 {
        self.journal_revision
    }

    pub fn bump_quota_epoch(&mut self) -> u32 {
        self.quota_epoch = self.quota_epoch.saturating_add(1);
        self.journal_revision = self.journal_revision.saturating_add(1);
        self.quota_epoch
    }

    pub fn bump_journal_revision(&mut self) -> u64 {
        self.journal_revision = self.journal_revision.saturating_add(1);
        self.journal_revision
    }

    pub fn seat_slice(&mut self, record: StoreRecord) {
        self.records.insert(record.slice_path.clone(), record);
        self.bump_journal_revision();
    }

    pub fn unseat_slice(&mut self, slice_path: &str) -> bool {
        if self.records.remove(slice_path).is_some() {
            self.bump_journal_revision();
            true
        } else {
            false
        }
    }

    pub fn slice_checksum(&self, slice_path: &str) -> Option<u32> {
        self.records.get(slice_path).map(|r| r.checksum)
    }

    pub fn drop_orphans(&mut self, epoch: u32) {
        self.records.retain(|_, rec| rec.epoch == epoch);
        self.bump_journal_revision();
    }

    pub fn record_count(&self) -> usize {
        self.records.len()
    }

    pub fn records_snapshot(&self) -> HashMap<String, StoreRecord> {
        self.records.clone()
    }

    pub fn restore_full_state(
        &mut self,
        records: HashMap<String, StoreRecord>,
        quota_epoch: u32,
        journal_revision: u64,
    ) {
        self.records = records;
        self.quota_epoch = quota_epoch;
        self.journal_revision = journal_revision;
    }

    pub fn load_from_file(path: &str) -> Result<Self, String> {
        let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        let data: StoredStore = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        let mut records = HashMap::new();
        for (key, mut rec) in data.records {
            if rec.slice_path.is_empty() {
                rec.slice_path = key.clone();
            }
            records.insert(key, rec);
        }
        Ok(Self {
            records,
            quota_epoch: data.quota_epoch,
            journal_revision: data.journal_revision,
        })
    }
}
