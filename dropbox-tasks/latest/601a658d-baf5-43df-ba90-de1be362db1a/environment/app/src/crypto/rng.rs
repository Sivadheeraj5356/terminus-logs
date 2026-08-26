use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static COUNTER: AtomicU64 = AtomicU64::new(0x9e3779b97f4a7c15);

fn seed() -> u64 {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0);
    let c = COUNTER.fetch_add(0x2545f4914f6cdd1d, Ordering::SeqCst);
    let mut x = nanos ^ c.rotate_left(17) ^ 0xd1b54a32d192ed03;
    x ^= x >> 33;
    x = x.wrapping_mul(0xff51afd7ed558ccd);
    x ^= x >> 33;
    x
}

fn next(state: &mut u64) -> u64 {
    let mut x = *state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    x
}

pub fn random_bytes(len: usize) -> Vec<u8> {
    let mut state = seed();
    if state == 0 {
        state = 0x1234567890abcdef;
    }
    let mut out = Vec::with_capacity(len);
    while out.len() < len {
        let value = next(&mut state);
        out.extend_from_slice(&value.to_le_bytes());
    }
    out.truncate(len);
    out
}

pub fn token_hex(bytes: usize) -> String {
    let raw = random_bytes(bytes);
    let mut out = String::with_capacity(bytes * 2);
    for b in raw {
        out.push_str(&format!("{:02x}", b));
    }
    out
}
