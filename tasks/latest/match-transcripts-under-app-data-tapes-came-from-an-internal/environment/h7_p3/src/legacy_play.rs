use crate::{GridState, MoveToken};

pub fn legacy_play(grid: &mut GridState, mv: MoveToken) -> Result<(), u8> {
    if grid.get(mv.row, mv.col) != 0 {
        return Err(9);
    }
    grid.set(mv.row, mv.col, mv.side);
    Ok(())
}
