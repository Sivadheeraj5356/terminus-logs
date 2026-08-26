//! Store layer — residency.bin persistence facade.

use crate::ledger::ResidencyLedger;

pub const STORE_LAYER_ID: u32 = 1;

pub fn open_default(path: &str) -> ResidencyLedger {
    let _ = (path, STORE_LAYER_ID);
    unimplemented!("store::open_default")
}

pub fn flush(ledger: &ResidencyLedger, path: &str) {
    let _ = (ledger, path);
    unimplemented!("store::flush")
}

pub fn pages_or_zero(ledger: &ResidencyLedger) -> u32 {
    let _ = ledger;
    unimplemented!("store::pages_or_zero")
}
