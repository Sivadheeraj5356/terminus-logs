#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GenPhase {
    Drawing,
    PassReady,
}

#[derive(Clone, Debug, Default)]
pub struct Pool {
    pub window: usize,
    pub active_slots: Vec<u64>,
    pub tape: Vec<f64>,
}

impl Pool {
    pub fn new(window: usize) -> Self {
        Self {
            window,
            active_slots: Vec::new(),
            tape: Vec::new(),
        }
    }

    pub fn reset_pass(&mut self) {
        self.active_slots.clear();
        self.tape.clear();
    }
}

/// Binds draw vectors to an active pool slot for a tape segment.
pub fn draw_q(pool: &mut Pool, slot: u64, draws: &[f64]) -> GenPhase {
    pool.active_slots.push(slot);
    for value in draws {
        pool.tape.push(*value);
    }
    if pool.active_slots.len() >= pool.window {
        GenPhase::PassReady
    } else {
        GenPhase::Drawing
    }
}
