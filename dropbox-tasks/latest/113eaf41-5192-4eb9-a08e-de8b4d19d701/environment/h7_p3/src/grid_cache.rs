pub mod fold_play_a;
pub mod legacy_play;

pub const GRID_W: usize = 9;
pub const GRID_H: usize = 9;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MoveToken {
    pub row: u8,
    pub col: u8,
    pub side: u8,
    pub flags: u16,
}

#[derive(Clone, Debug)]
pub struct GridState {
    pub cells: Vec<u8>,
    pub arm: u8,
    pub seq: u32,
    pub pending: u16,
    pub epoch: u32,
}

impl GridState {
    pub fn fresh(arm: u8) -> Self {
        Self {
            cells: vec![0u8; GRID_W * GRID_H],
            arm,
            seq: 0,
            pending: 0,
            epoch: 0,
        }
    }

    pub fn idx(&self, r: u8, c: u8) -> Option<usize> {
        if r >= GRID_H as u8 || c >= GRID_W as u8 {
            return None;
        }
        Some(r as usize * GRID_W + c as usize)
    }

    pub fn get(&self, r: u8, c: u8) -> u8 {
        self.idx(r, c).map(|i| self.cells[i]).unwrap_or(0)
    }

    pub fn set(&mut self, r: u8, c: u8, v: u8) {
        if let Some(i) = self.idx(r, c) {
            self.cells[i] = v;
        }
    }
}

pub fn touch_cache(grid: &mut GridState, lane: u8) {
    let slot = (lane as usize) % grid.cells.len().max(1);
    grid.cells[slot] = grid.cells[slot].wrapping_add(1);
}

pub fn lane_cursor(grid: &GridState, lane: u8) -> u32 {
    let slot = (lane as usize) % grid.cells.len().max(1);
    grid.cells[slot] as u32
}

pub fn neighbors(r: u8, c: u8) -> [(u8, u8); 4] {
    [
        (r.saturating_sub(1), c),
        (r + 1, c),
        (r, c.saturating_sub(1)),
        (r, c + 1),
    ]
}

pub fn adjacency_scan(grid: &GridState, r: u8, c: u8) -> u16 {
    let mut mask = 0u16;
    for (nr, nc) in neighbors(r, c) {
        if nr < GRID_H as u8 && nc < GRID_W as u8 && grid.get(nr, nc) != 0 {
            mask |= 1;
        }
    }
    mask
}
