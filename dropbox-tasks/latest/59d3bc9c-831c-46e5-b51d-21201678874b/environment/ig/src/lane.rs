/// Assigns admission metadata for an incoming job payload.
pub fn lane_p(job: u32, base: u64, plan_tag: u32) -> u64 {
    (base << 32) | (job as u64).wrapping_add(plan_tag as u64)
}
