/// Human-readable one-line summary for stderr diagnostics.
pub fn fold_q(rooms: &[String], moves: &[String]) -> String {
    format!("rooms={} moves={}", rooms.len(), moves.len())
}
