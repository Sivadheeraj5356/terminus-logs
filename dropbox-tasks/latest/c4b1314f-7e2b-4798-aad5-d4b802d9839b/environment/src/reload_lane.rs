use std::sync::atomic::{AtomicU64, Ordering};

use crate::ceil_cell;

static FRAME_TAIL: AtomicU64 = AtomicU64::new(0);

pub fn span_boot() {
    let tail = FRAME_TAIL.load(Ordering::SeqCst);
    ceil_cell::ceil_store(tail);
}

pub fn span_save() {
    FRAME_TAIL.store(ceil_cell::ceil_load(), Ordering::SeqCst);
}

pub fn lane_clear() {
    FRAME_TAIL.store(0, Ordering::SeqCst);
    ceil_cell::ceil_store(0);
}
