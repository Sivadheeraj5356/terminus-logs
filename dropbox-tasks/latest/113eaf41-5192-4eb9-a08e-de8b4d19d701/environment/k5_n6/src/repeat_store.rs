pub mod eval_repeat_c;
pub mod stub_repeat;

use std::collections::VecDeque;

#[derive(Clone, Debug)]
pub struct RepeatStore {
    pub journal: VecDeque<u64>,
    pub generation: u32,
    pub last_hash: u64,
}

impl RepeatStore {
    pub fn fresh() -> Self {
        Self {
            journal: VecDeque::new(),
            generation: 0,
            last_hash: 0,
        }
    }

    pub fn push_board(&mut self, digest: u64) {
        self.journal.push_back(digest);
        if self.journal.len() > 64 {
            self.journal.pop_front();
        }
        self.last_hash = digest;
    }

    pub fn export_tail(&self) -> String {
        self.journal
            .iter()
            .map(|v| format!("{:016x}", v))
            .collect::<Vec<_>>()
            .join(":")
    }
}
