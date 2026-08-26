pub fn seal_allowed(scheduler_phys: &[u32], proposed_phys: &[u32]) -> bool {
    let mut a = scheduler_phys.to_vec();
    let mut b = proposed_phys.to_vec();
    a.sort_unstable();
    b.sort_unstable();
    a == b
}

pub fn note_mutation(tag: &str, epoch: u32) -> u64 {
    let mut h = 0xcbf29ce484222325u64;
    for b in tag.bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h ^= epoch as u64;
    h
}

pub fn require_nonzero_pages(pages: u32) -> bool {
    pages > 0
}
