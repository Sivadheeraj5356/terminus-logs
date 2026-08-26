use crate::ledger::SeatLedger;
use crate::shift_table::materialize_shift_table;
use serde_json::Value;

static mut CACHE_EPOCH: u32 = u32::MAX;
static mut CACHE_REV: u64 = u64::MAX;
static mut CACHE_BLOB: Option<Value> = None;

pub fn cached_shift_table(index: &SeatLedger) -> Value {
    let epoch = index.cycle_epoch();
    let rev = index.journal_revision();
    unsafe {
        if let Some(blob) = &CACHE_BLOB {
            if epoch == CACHE_EPOCH && rev == CACHE_REV {
                return blob.clone();
            }
        }
        let snap = materialize_shift_table(index);
        CACHE_EPOCH = epoch;
        CACHE_REV = rev;
        CACHE_BLOB = Some(snap.clone());
        snap
    }
}

pub fn reset_shift_cache_for_tests() {
    unsafe {
        CACHE_EPOCH = u32::MAX;
        CACHE_REV = u64::MAX;
        CACHE_BLOB = None;
    }
}
