use spawn::PendingLane;
use persist::{read_manifest, read_slot_sidecar, Store, VaultMark};

#[derive(Clone, Debug)]
pub struct CyclePlan {
    pub halt_pass: u32,
    pub carry_slots: Vec<u64>,
    pub lane: PendingLane,
}

pub fn continue_from_vault(store: &Store, pending: &mut PendingLane) -> CyclePlan {
    spin_s(store, pending)
}

/// Builds continue plan from persisted marks and pending lane state.
pub fn spin_s(store: &Store, pending: &mut PendingLane) -> CyclePlan {
    let mark = read_manifest(store).unwrap_or(VaultMark {
        last_generation: 0,
        last_pass: 0,
        open_count: 0,
    });
    let mut carry: Vec<u64> = (0..mark.open_count as u64)
        .map(|idx| mark.last_generation.wrapping_sub(idx))
        .collect();
    carry.sort_unstable();
    for item in &pending.items {
        carry.push(item.slot);
    }
    carry.sort_unstable();
    CyclePlan {
        halt_pass: mark.last_pass,
        carry_slots: carry,
        lane: std::mem::take(pending),
    }
}
