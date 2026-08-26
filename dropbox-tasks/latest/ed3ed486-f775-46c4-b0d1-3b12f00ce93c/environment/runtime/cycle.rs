use crate::q_in::PendingLane;
use crate::q_st::{hydrate_tags, read_manifest, SealMark, Store};

#[derive(Clone, Debug)]
pub struct CyclePlan {
    pub resume_step: u32,
    pub wave_offset: u32,
    pub replay_tags: Vec<u64>,
    pub lane: PendingLane,
}

pub fn resume_from_vault(store: &Store, pending: &mut PendingLane) -> CyclePlan {
    spin_h(store, pending)
}

/// Builds continue plan from persisted marks and pending lane state.
pub fn spin_h(store: &Store, pending: &mut PendingLane) -> CyclePlan {
    let mark = read_manifest(store).unwrap_or(SealMark {
        last_tag: 0,
        last_step: 0,
        pending_count: 0,
        wave_offset: 0,
    });
    let mut replay: Vec<u64> = (0..mark.pending_count as u64)
        .map(|idx| mark.last_tag.wrapping_sub(idx))
        .collect();
    replay.sort_unstable();
    if replay.is_empty() {
        replay = hydrate_tags(store);
    }
    for item in &pending.items {
        replay.push(item.slot as u64);
    }
    replay.sort_unstable();
    CyclePlan {
        resume_step: mark.last_step,
        wave_offset: mark.wave_offset,
        replay_tags: replay,
        lane: std::mem::take(pending),
    }
}
