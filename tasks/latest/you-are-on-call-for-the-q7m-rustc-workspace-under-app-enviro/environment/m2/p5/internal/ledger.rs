#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MoveClass {
    Quiet,
    Irreversible,
}

pub fn ledger_mark(mv: &str, captured: bool) -> MoveClass {
    if captured {
        return MoveClass::Irreversible;
    }
    if mv.len() == 4 {
        let from_rank = mv.as_bytes()[1];
        let to_rank = mv.as_bytes()[3];
        let from_file = mv.as_bytes()[0];
        let to_file = mv.as_bytes()[2];
        if from_rank == b'2' || from_rank == b'7' {
            if (from_rank as i8 - to_rank as i8).abs() == 2 {
                return MoveClass::Irreversible;
            }
        }
        if from_file == b'e' && (to_file == b'g' || to_file == b'c') {
            return MoveClass::Irreversible;
        }
    }
    MoveClass::Quiet
}
