pub fn marks(data: &[u8]) -> Vec<usize> {
    let mut out = Vec::new();
    let mut acc: u32 = 0;
    for (idx, b) in data.iter().enumerate() {
        acc = acc.rotate_left(5) ^ (*b as u32) ^ (idx as u32);
        if idx > 0 && (acc & 0x1f) == 0x0b {
            out.push(idx + 1);
        }
    }
    out
}

pub fn window_score(data: &[u8]) -> u32 {
    data.iter().fold(0u32, |acc, b| acc.rotate_left(3) ^ (*b as u32))
}
