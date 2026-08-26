//! Optional run counters for local profiling; not consulted by adjudication.

#[derive(Default, Debug, Clone)]
pub struct Counters {
    pub moves: u64,
    pub strikes: u64,
    pub overwatches: u64,
}

impl Counters {
    pub fn bump_move(&mut self) {
        self.moves += 1;
    }

    pub fn bump_strike(&mut self) {
        self.strikes += 1;
    }

    pub fn bump_overwatch(&mut self) {
        self.overwatches += 1;
    }

    pub fn total(&self) -> u64 {
        self.moves + self.strikes + self.overwatches
    }
}
