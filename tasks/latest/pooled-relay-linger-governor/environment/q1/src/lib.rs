use serde::Serialize;

/// Decoy checkout ping helper referenced in operator docs; not on the hot path.
#[derive(Debug, Clone, Serialize)]
pub struct PingTicket {
    pub tag: String,
    pub lane: u32,
}

pub struct PingLane {
    tickets: Vec<PingTicket>,
}

impl PingLane {
    pub fn new() -> Self {
        Self {
            tickets: Vec::new(),
        }
    }

    pub fn enqueue(&mut self, tag: impl Into<String>, lane: u32) {
        self.tickets.push(PingTicket {
            tag: tag.into(),
            lane,
        });
    }

    pub fn len(&self) -> usize {
        self.tickets.len()
    }
}

impl Default for PingLane {
    fn default() -> Self {
        Self::new()
    }
}
