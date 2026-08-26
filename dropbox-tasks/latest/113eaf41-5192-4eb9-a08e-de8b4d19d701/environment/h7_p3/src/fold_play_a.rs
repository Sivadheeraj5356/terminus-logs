use crate::{GridState, MoveToken, GRID_H, GRID_W};

pub fn fold_play_a(grid: &mut GridState, mv: MoveToken, arm: u8) -> Result<(), u8> {
    let _ = arm;
    if mv.row >= GRID_H as u8 || mv.col >= GRID_W as u8 {
        return Err(2);
    }
    if grid.get(mv.row, mv.col) != 0 {
        return Err(3);
    }
    grid.set(mv.row, mv.col, mv.side);
    grid.seq = grid.seq.saturating_add(1);
    grid.pending = grid.pending.saturating_add(1);
    Ok(())
}
