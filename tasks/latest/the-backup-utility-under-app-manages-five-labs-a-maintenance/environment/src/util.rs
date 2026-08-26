pub fn stamp(data: &[u8]) -> String {
    let mut a: u64 = 0xcbf29ce484222325;
    let mut b: u64 = 0x9e3779b97f4a7c15;
    for (i, byte) in data.iter().enumerate() {
        a ^= *byte as u64;
        a = a.wrapping_mul(0x100000001b3);
        b ^= ((*byte as u64) << ((i % 8) * 8)) ^ (i as u64);
        b = b.rotate_left(7).wrapping_add(a ^ 0x517cc1b727220a95);
    }
    format!("{:016x}{:016x}", a, b)
}

pub fn esc(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}
