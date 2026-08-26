pub fn quick_a(data: &[u8]) -> u32 {
    data.iter().filter(|b| **b > 0).count() as u32
}
