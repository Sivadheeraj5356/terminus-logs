use crate::errors::StreamError;
use crate::queue::EventQueue;
use std::collections::BTreeSet;

#[derive(Clone, Debug, Default)]
pub struct ResourceTable {
    next: u32,
    open: BTreeSet<u32>,
    dropped: usize,
    queue: EventQueue,
}

impl ResourceTable {
    pub fn new() -> Self {
        Self {
            next: 1,
            open: BTreeSet::new(),
            dropped: 0,
            queue: EventQueue::default(),
        }
    }

    pub fn open_stream(&mut self) -> u32 {
        let descriptor = self.next;
        self.next += 1;
        self.open.insert(descriptor);
        descriptor
    }

    pub fn close_stream(&mut self, descriptor: u32) {
        if self.open.remove(&descriptor) {
            self.dropped += 1;
        }
    }

    pub fn park_error(&mut self, error: StreamError) {
        self.queue.push(error);
    }

    pub fn release_after_error(&mut self, descriptor: u32) {
        let _ = self.queue.drain_descriptor(descriptor);
    }

    pub fn opened(&self) -> usize {
        (self.next - 1) as usize
    }

    pub fn dropped(&self) -> usize {
        self.dropped
    }

    pub fn leaked(&self) -> usize {
        self.open.len() + self.queue.len()
    }
}
