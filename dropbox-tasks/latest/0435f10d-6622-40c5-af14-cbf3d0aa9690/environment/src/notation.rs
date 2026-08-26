use crate::board::Board;

#[derive(Clone, Copy)]
pub enum Move {
    Play(usize),
    Pass,
}

pub fn parse_log(text: &str, board: &Board) -> Result<Vec<Move>, String> {
    let mut moves = Vec::new();
    for raw in text.lines() {
        let line = raw.split('#').next().unwrap().trim();
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() != 1 {
            return Err(format!("move must be a single token: {line}"));
        }
        let tok = parts[0];
        if tok == "pass" {
            moves.push(Move::Pass);
        } else if let Some(&i) = board.index.get(tok) {
            moves.push(Move::Play(i));
        } else {
            return Err(format!("unknown intersection {tok}"));
        }
    }
    Ok(moves)
}
