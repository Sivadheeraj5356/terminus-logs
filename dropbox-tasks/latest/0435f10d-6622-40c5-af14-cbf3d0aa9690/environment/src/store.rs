pub struct Row {
    pub game_id: String,
    pub first_illegal: i64,
    pub reason: String,
    pub black_score: u64,
    pub white_score: u64,
    pub black_captures: u64,
    pub white_captures: u64,
    pub moves_played: u64,
    pub final_board: String,
}

pub fn write_rows(_db: &str, _rows: &[Row]) -> Result<(), String> {
    todo!()
}

pub fn query(_db: &str, _sql: &str) -> Result<Vec<Vec<String>>, String> {
    todo!()
}
