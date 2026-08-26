use serde::Serialize;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StepPhase {
    Folding,
    StepReady,
}

#[derive(Clone, Debug, Default)]
pub struct AccBuf {
    pub window: usize,
    pub tags: Vec<u64>,
    pub acc: Vec<f32>,
}

impl AccBuf {
    pub fn new(window: usize) -> Self {
        Self {
            window,
            tags: Vec::new(),
            acc: Vec::new(),
        }
    }

    pub fn reset_window(&mut self) {
        self.tags.clear();
        self.acc.clear();
    }
}

/// Folds incoming slices into the active accumulator buffer.
pub fn fold_u(buf: &mut AccBuf, tag: u64, slice: &[f32]) -> StepPhase {
    buf.tags.push(tag);
    for (idx, value) in slice.iter().enumerate() {
        if idx < buf.acc.len() {
            buf.acc[idx] += value;
        } else {
            buf.acc.push(*value);
        }
    }
    if buf.tags.len() >= buf.window {
        StepPhase::StepReady
    } else {
        StepPhase::Folding
    }
}

#[derive(Serialize)]
pub struct GaugeView {
    pub l2_norm: f64,
    pub within_plan: bool,
}
