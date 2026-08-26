//! Replay / temporal epoch layer — advance + compact.

pub const REPLAY_LAYER_ID: u32 = 2;

#[derive(Debug, Clone, Copy)]
pub struct ReplayOpts {
    pub compact: bool,
    pub threshold: f64,
}

impl ReplayOpts {
    pub fn default_opts(threshold: f64) -> Self {
        Self { compact: false, threshold }
    }
}

pub fn bump_epoch_once(epoch: &mut u32) {
    let _ = (epoch, REPLAY_LAYER_ID);
    unimplemented!("replay::bump_epoch_once")
}

pub fn maybe_compact(free_ratio: f64, opts: &ReplayOpts) -> bool {
    let _ = (free_ratio, opts);
    unimplemented!("replay::maybe_compact")
}
