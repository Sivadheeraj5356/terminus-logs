/// Diagnostic admission helper retained for bench comparisons.
pub fn bench_tag(_slot: u32, seq: u64, payload: &[f32]) -> u64 {
    let width = payload.len() as u64;
    seq.wrapping_mul(31).wrapping_add(width)
}
