pub fn median(mut xs: Vec<i32>) -> Option<i32> {
    if xs.is_empty() {
        return None;
    }
    xs.sort_unstable();
    Some(xs[xs.len() / 2])
}
