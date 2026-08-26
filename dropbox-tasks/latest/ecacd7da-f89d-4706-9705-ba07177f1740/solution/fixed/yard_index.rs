use crate::ledger::SeatLedger;
use crate::shift_table::materialize_shift_table;
use serde_json::Value;

static mut CACHE_EPOCH: u32 = u32::MAX;
static mut CACHE_REV: u64 = u64::MAX;
static mut CACHE_FP: u64 = u64::MAX;
static mut CACHE_IDENTITY: Option<Vec<u8>> = None;
static mut CACHE_BLOB: Option<Value> = None;

fn compact_fingerprint(index: &SeatLedger) -> u64 {
    let epoch = index.cycle_epoch() as u64;
    let rev = index.journal_revision();
    (epoch << 32) | (rev & 0xFFFF_FFFF)
}

pub fn cached_shift_table(index: &SeatLedger) -> Value {
    let epoch = index.cycle_epoch();
    let rev = index.journal_revision();
    let fp = compact_fingerprint(index);
    let identity = index.semantic_identity();
    unsafe {
        if let Some(blob) = &CACHE_BLOB {
            if epoch == CACHE_EPOCH
                && rev == CACHE_REV
                && fp == CACHE_FP
                && CACHE_IDENTITY.as_deref() == Some(identity.as_slice())
            {
                return blob.clone();
            }
        }
        let snap = materialize_shift_table(index);
        CACHE_EPOCH = epoch;
        CACHE_REV = rev;
        CACHE_FP = fp;
        CACHE_IDENTITY = Some(identity);
        CACHE_BLOB = Some(snap.clone());
        snap
    }
}

pub fn reset_shift_cache_for_tests() {
    unsafe {
        CACHE_EPOCH = u32::MAX;
        CACHE_REV = u64::MAX;
        CACHE_FP = u64::MAX;
        CACHE_IDENTITY = None;
        CACHE_BLOB = None;
    }
}
