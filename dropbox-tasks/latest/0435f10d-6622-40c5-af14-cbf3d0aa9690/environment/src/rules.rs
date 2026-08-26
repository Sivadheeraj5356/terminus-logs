use crate::board::Board;
use crate::notation::Move;

pub const EMPTY: u8 = 0;
pub const BLACK: u8 = 1;
pub const WHITE: u8 = 2;

pub struct Outcome {
    pub first_illegal: i64,
    pub reason: String,
    pub state: Vec<u8>,
    pub black_captures: u64,
    pub white_captures: u64,
    pub moves_played: u64,
}

pub fn component(_start: usize, _want: u8, _state: &[u8], _board: &Board) -> Vec<usize> {
    todo!()
}

pub fn liberties(_group: &[usize], _state: &[u8], _board: &Board) -> usize {
    todo!()
}

pub fn canonical(_state: &[u8], _board: &Board) -> String {
    todo!()
}

pub fn replay(_moves: &[Move], _board: &Board) -> Outcome {
    todo!()
}
