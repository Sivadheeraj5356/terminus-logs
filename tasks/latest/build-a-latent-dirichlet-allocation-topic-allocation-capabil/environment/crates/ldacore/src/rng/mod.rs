pub fn seed_state(seed: u64) -> u64 {
    if seed == 0 {
        0x9E37_79B9_7F4A_7C15
    } else {
        seed
    }
}

pub fn next_u64(state: &mut u64) -> u64 {
    let mut x = *state;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    *state = x;
    x.wrapping_mul(0x2545_F491_4F6C_DD1F)
}

pub fn uniform(state: &mut u64) -> f64 {
    let bits = next_u64(state) >> 11;
    bits as f64 * (1.0 / 9007199254740992.0)
}

pub fn init_topic(state: &mut u64, k: usize, token_index: usize) -> usize {
    let _ = next_u64(state);
    token_index % k
}
