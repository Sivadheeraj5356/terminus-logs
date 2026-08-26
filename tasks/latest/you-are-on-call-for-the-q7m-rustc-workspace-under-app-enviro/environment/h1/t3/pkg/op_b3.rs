use crate::GridView;

pub fn op_b3(grid: &GridView) -> i32 {
    let mut score = 0i32;
    for c in grid.cells {
        let v = match c.to_ascii_lowercase() {
            b'p' => 1,
            b'n' | b'b' => 3,
            b'r' => 5,
            b'q' => 9,
            _ => 0,
        };
        if c.is_ascii_uppercase() {
            score += v;
        } else if c.is_ascii_lowercase() {
            score -= v;
        }
    }
    score
}
