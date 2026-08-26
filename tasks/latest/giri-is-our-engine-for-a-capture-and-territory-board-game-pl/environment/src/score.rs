use crate::board::Board;

pub fn area_score(_state: &[u8], _board: &Board) -> (u64, u64) {
    todo!()
}

pub struct Comp {
    pub kind: &'static str,
    pub color: &'static str,
    pub members: Vec<usize>,
}

pub fn components(_state: &[u8], _board: &Board) -> Vec<Comp> {
    todo!()
}

pub fn dot(_state: &[u8], _board: &Board) -> String {
    todo!()
}

pub fn parse_board_str(_s: &str, _board: &Board) -> Vec<u8> {
    todo!()
}
