use crate::rho::RowPt;

pub fn linear_at(samples: &[RowPt], pos: f64) -> [f64; 4] {
    if samples.is_empty() {
        return [0.0; 4];
    }
    if samples.len() == 1 {
        let s = &samples[0];
        return [s.cyan, s.magenta, s.yellow, s.silver];
    }
    let mut left = &samples[0];
    let mut right = &samples[samples.len() - 1];
    for w in samples.windows(2) {
        if w[0].pos <= pos && pos <= w[1].pos {
            left = &w[0];
            right = &w[1];
            break;
        }
    }
    if (right.pos - left.pos).abs() < 1e-12 {
        return [left.cyan, left.magenta, left.yellow, left.silver];
    }
    let t = (pos - left.pos) / (right.pos - left.pos);
    [
        left.cyan + t * (right.cyan - left.cyan),
        left.magenta + t * (right.magenta - left.magenta),
        left.yellow + t * (right.yellow - left.yellow),
        left.silver + t * (right.silver - left.silver),
    ]
}
