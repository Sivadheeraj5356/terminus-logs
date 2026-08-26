pub fn dot(a: &[i32], b: &[i32]) -> i64 {
    a.iter()
        .zip(b)
        .map(|(x, y)| i64::from(*x) * i64::from(*y))
        .sum()
}
