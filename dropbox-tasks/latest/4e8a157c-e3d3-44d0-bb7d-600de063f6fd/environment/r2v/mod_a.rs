mod scan_help;

pub fn walk_q3(step_ix: u32, family_ix: u32, prev: u64) -> u64 {
    let tag = (step_ix as u64).wrapping_mul(149) + (family_ix as u64).wrapping_mul(23);
    prev.wrapping_add(tag)
}
