use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
pub struct SegmentView {
    pub slot: u64,
    pub len: usize,
}

pub fn record_segment(slot: u64, draws: &[f64]) -> SegmentView {
    SegmentView {
        slot,
        len: draws.len(),
    }
}
