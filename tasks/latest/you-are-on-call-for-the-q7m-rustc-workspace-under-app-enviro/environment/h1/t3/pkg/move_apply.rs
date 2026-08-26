use crate::{GridView, Rights, Sq};

pub fn apply_uci(grid: &mut GridView, rights: &mut Rights, ep: &mut Option<Sq>, mv: &str) -> bool {
    if mv.len() != 4 {
        return false;
    }
    let f0 = (mv.as_bytes()[0] - b'a') as i32;
    let r0 = (mv.as_bytes()[1] - b'1') as i32;
    let f1 = (mv.as_bytes()[2] - b'a') as i32;
    let r1 = (mv.as_bytes()[3] - b'1') as i32;
    if f0 < 0 || f0 > 7 || r0 < 0 || r0 > 7 || f1 < 0 || f1 > 7 || r1 < 0 || r1 > 7 {
        return false;
    }
    let from = (r0 * 8 + f0) as usize;
    let to = (r1 * 8 + f1) as usize;
    let piece = grid.cells[from];
    if piece == b' ' {
        return false;
    }
    let is_white = piece.is_ascii_uppercase();
    if is_white != grid.side_white {
        return false;
    }
    let captured = grid.cells[to];
    grid.cells[to] = piece;
    grid.cells[from] = b' ';
    *ep = None;
    let pr = piece.to_ascii_lowercase();
    if pr == b'p' {
        let diff = (r1 - r0).abs();
        if diff == 2 {
            *ep = Some((r0 * 8 + f0) as Sq);
        }
    }
    if pr == b'k' {
        if is_white {
            rights.k = false;
            rights.q = false;
        } else {
            rights.kk = false;
            rights.qq = false;
        }
    }
    if pr == b'r' {
        if is_white {
            if from == 0 {
                rights.q = false;
            }
            if from == 7 {
                rights.k = false;
            }
        } else if from == 56 {
            rights.qq = false;
        } else if from == 63 {
            rights.kk = false;
        }
    }
    if captured != b' ' {
        // capture clears ep already
    }
    grid.side_white = !grid.side_white;
    true
}
