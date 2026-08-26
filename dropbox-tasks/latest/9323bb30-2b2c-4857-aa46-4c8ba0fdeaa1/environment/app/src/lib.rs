//! KV-tile residency coordinator — greenfield stubs.

pub mod pack;
pub mod profile;
pub mod plan;
pub mod advance;
pub mod seal;
pub mod ledger;
pub mod store;
pub mod replay;
pub mod finalize;
pub mod internal;

pub fn wiring_gap() -> ! {
    unimplemented!("wiring_gap")
}
