/// Single-thread admission path kept for diagnostics.
pub fn shadow_lane(job: u32, base: u64) -> u64 {
    (job as u64) ^ base.rotate_left(7)
}

pub fn shadow_queue_len(items: &[u32]) -> usize {
    items.len()
}
