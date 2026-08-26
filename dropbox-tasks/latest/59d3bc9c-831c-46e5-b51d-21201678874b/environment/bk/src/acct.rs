use super::Pool;

pub fn slots_for_pass(pool: &Pool) -> Vec<u64> {
    pool.active_slots.clone()
}

pub fn slot_tally(spawn_total: u64, window: u64, pass_total: u64) -> i64 {
    spawn_total as i64 - (window as i64 * pass_total as i64)
}
