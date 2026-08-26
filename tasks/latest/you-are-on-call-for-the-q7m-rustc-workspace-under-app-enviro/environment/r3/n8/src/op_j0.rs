use h1_t3::GridView;

fn piece_slot(cell: u8) -> Option<(usize, usize)> {
    if cell == b' ' {
        return None;
    }
    let kind = match cell.to_ascii_lowercase() {
        b'p' => 0,
        b'n' => 1,
        b'b' => 2,
        b'r' => 3,
        b'q' => 4,
        b'k' => 5,
        _ => return None,
    };
    let color = if cell.is_ascii_uppercase() { 0 } else { 1 };
    Some((kind, color))
}

fn table_entry(sq: usize, kind: usize, color: usize) -> u64 {
    let idx = sq.wrapping_mul(12).wrapping_add(kind.wrapping_mul(2)).wrapping_add(color);
    let seed = 0xD6E8FEB86659FD93_u64 ^ idx as u64;
    seed.wrapping_mul(0x100000001B3).rotate_left((idx % 41) as u32)
}

pub fn op_j0(grid: &GridView) -> u64 {
    let mut h = 0xA0761D6478BD642F_u64;
    for (sq, &cell) in grid.cells.iter().enumerate() {
        if let Some((kind, color)) = piece_slot(cell) {
            h ^= table_entry(sq, kind, color);
        }
    }
    if grid.side_white {
        h ^= 0x55;
    } else {
        h ^= 0xAA;
    }
    h
}
