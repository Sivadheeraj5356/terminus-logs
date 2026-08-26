use crate::errors::StreamError;
use std::collections::VecDeque;

#[derive(Clone, Debug, Default)]
pub struct EventQueue {
    pending: VecDeque<StreamError>,
}

impl EventQueue {
    pub fn push(&mut self, error: StreamError) {
        self.pending.push_back(error);
    }

    pub fn drain_descriptor(&mut self, descriptor: u32) -> bool {
        if let Some(index) = self
            .pending
            .iter()
            .position(|event| event.descriptor == descriptor)
        {
            self.pending.remove(index);
            return true;
        }
        false
    }

    pub fn len(&self) -> usize {
        self.pending.len()
    }
}
