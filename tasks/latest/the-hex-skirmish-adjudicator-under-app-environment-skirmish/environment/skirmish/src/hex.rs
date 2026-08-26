/// Axial-style grid helpers used by movement and ranging.

pub fn neighbors(x: i32, y: i32) -> [[i32; 2]; 6] {
    [
        [x + 1, y],
        [x - 1, y],
        [x, y + 1],
        [x, y - 1],
        [x + 1, y - 1],
        [x - 1, y + 1],
    ]
}

pub fn in_bounds(width: i32, height: i32, x: i32, y: i32) -> bool {
    x >= 0 && y >= 0 && x < width && y < height
}

pub fn distance(a: [i32; 2], b: [i32; 2]) -> i32 {
    let dx = (a[0] - b[0]).abs();
    let dy = (a[1] - b[1]).abs();
    dx + dy
}

/// Inclusive line of hex cells from a to b (stable for determinism).
pub fn hex_line(a: [i32; 2], b: [i32; 2]) -> Vec<[i32; 2]> {
    let n = crate::hex::cube_distance(a, b).max(1);
    let mut out = Vec::with_capacity((n + 1) as usize);
    for i in 0..=n {
        let t = i as f64 / n as f64;
        let x = (a[0] as f64 + (b[0] - a[0]) as f64 * t).round() as i32;
        let y = (a[1] as f64 + (b[1] - a[1]) as f64 * t).round() as i32;
        if out.last().copied() != Some([x, y]) {
            out.push([x, y]);
        }
    }
    if out.last().copied() != Some(b) {
        out.push(b);
    }
    out
}

pub fn cube_distance(a: [i32; 2], b: [i32; 2]) -> i32 {
    let dx = (a[0] - b[0]).abs();
    let dy = (a[1] - b[1]).abs();
    let dz = ((a[0] + a[1]) - (b[0] + b[1])).abs();
    dx.max(dy).max(dz)
}
