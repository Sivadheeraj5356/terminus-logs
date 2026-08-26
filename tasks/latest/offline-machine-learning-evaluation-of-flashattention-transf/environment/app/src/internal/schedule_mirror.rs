//! Combinatorial Blueprint: plan materializes a disk schedule.mir witness; seal folds CRC32 of
//! those bytes so in-memory visit_checksum alone cannot seal correctly.
//! Axiomatic Blindspot: SCH1 + visit triples ⇒ CRC axiom.
//! Silent Failure: skipping mir write or hashing CRC(visit_checksum) instead of file bytes.

use super::app_root;
use anyhow::Result;

pub fn mir_path() -> String {
    app_root::join_str("data/schedule.mir")
}

pub fn crc32_ieee(data: &[u8]) -> u32 {
    let _ = data;
    unimplemented!("schedule_mirror::crc32_ieee")
}

pub fn write_schedule_mir(visits: &[(u32, u32, u32)]) -> Result<()> {
    let _ = (visits, mir_path());
    unimplemented!("schedule_mirror::write_schedule_mir")
}

pub fn clear_schedule_mir() {
    let _ = mir_path();
    unimplemented!("schedule_mirror::clear_schedule_mir")
}

pub fn schedule_crc_from_disk() -> u32 {
    let _ = mir_path();
    unimplemented!("schedule_mirror::schedule_crc_from_disk")
}
