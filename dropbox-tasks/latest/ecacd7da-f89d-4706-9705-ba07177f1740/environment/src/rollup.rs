use crate::cache_key::rollup_generation_key;
use crate::store::Store;
use serde_json::{json, Value};
use std::collections::BTreeMap;

static mut CACHE_KEY: u64 = u64::MAX;
static mut CACHE_BLOB: Option<Value> = None;

pub fn cached_rollup(store: &Store) -> Value {
    let key = rollup_generation_key(store.quota_epoch(), store.journal_revision());
    unsafe {
        if let Some(blob) = &CACHE_BLOB {
            if key == CACHE_KEY {
                return blob.clone();
            }
        }
        let mut slices = BTreeMap::new();
        for (path, rec) in store.records_snapshot() {
            slices.insert(
                path,
                json!({
                    "checksum": rec.checksum,
                    "epoch": rec.epoch,
                    "memory_bytes": rec.memory_bytes,
                }),
            );
        }
        let snap = json!({
            "quota_epoch": store.quota_epoch(),
            "journal_revision": store.journal_revision(),
            "slices": slices,
            "slice_count": slices.len(),
        });
        CACHE_KEY = key;
        CACHE_BLOB = Some(snap.clone());
        snap
    }
}

pub fn reset_cache_for_tests() {
    unsafe {
        CACHE_KEY = u64::MAX;
        CACHE_BLOB = None;
    }
}
