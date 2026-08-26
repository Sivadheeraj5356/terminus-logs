pub fn threshold(total_power: u64) -> u64 {
    (2 * total_power + 2) / 3
}
