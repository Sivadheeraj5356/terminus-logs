pub struct EpochTracker {
    current_epoch: u32,
}

impl EpochTracker {
    pub fn new() -> Self {
        Self { current_epoch: 0 }
    }

    pub fn current(&self) -> u32 {
        self.current_epoch
    }

    pub fn on_quota_open(&mut self, journal_epoch: u32) {
        self.current_epoch = journal_epoch;
    }
}
