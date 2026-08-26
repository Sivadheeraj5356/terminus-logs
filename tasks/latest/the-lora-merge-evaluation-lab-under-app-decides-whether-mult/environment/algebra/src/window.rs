pub fn rolling(xs: &[i32], width: usize) -> Vec<i32> {
    if width == 0 || width > xs.len() {
        return Vec::new();
    }
    xs.windows(width).map(|w| w.iter().sum()).collect()
}
