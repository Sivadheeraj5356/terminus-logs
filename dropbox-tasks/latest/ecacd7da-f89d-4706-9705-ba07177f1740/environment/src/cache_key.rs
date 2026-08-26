pub fn rollup_generation_key(quota_epoch: u32, journal_revision: u64) -> u64 {
    ((quota_epoch as u64) << 32) | (journal_revision & 0xFFFF_FFFF)
}
