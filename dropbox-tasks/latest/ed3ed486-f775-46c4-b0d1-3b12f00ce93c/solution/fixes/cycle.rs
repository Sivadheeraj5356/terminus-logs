use crate::q_in::PendingLane;
use crate::q_st::{read_manifest, read_tag_sidecar, SealMark, Store};

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
    let mut replay = read_tag_sidecar(store);
    if replay.is_empty() {
        replay = crate::q_st::hydrate_tags(store);
    }
    for item in &pending.items {
        if !replay.contains(&item.tag) {
            replay.push(item.tag);
        }
    }
    CyclePlan {
        resume_step: mark.last_step,
        wave_offset: mark.wave_offset,
        replay_tags: replay,
        lane: std::mem::take(pending),
    }
}
