pub fn skip_b(counters: &mut [u32]) -> u32 {
    for c in counters {
        *c = 0;
    }
    0
}
