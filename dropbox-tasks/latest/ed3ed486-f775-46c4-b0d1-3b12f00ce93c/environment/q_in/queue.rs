use super::admit::mesh_k;

#[derive(Clone, Debug)]
pub struct LaneItem {
    pub slot: u32,
    pub tag: u64,
    pub payload: Vec<f32>,
}

#[derive(Clone, Debug, Default)]
pub struct PendingLane {
    pub items: Vec<LaneItem>,
}

impl PendingLane {
    pub fn admit(&mut self, slot: u32, seq: u64, payload: &[f32]) -> u64 {
        let tag = mesh_k(slot, seq, payload);
        self.items.push(LaneItem {
            slot,
            tag,
            payload: payload.to_vec(),
        });
        tag
    }

    pub fn drain_sorted(&mut self) -> Vec<LaneItem> {
        let mut out = std::mem::take(&mut self.items);
        out.sort_by_key(|item| item.slot);
        out
    }

    pub fn pending_slots(&self) -> Vec<i32> {
        let mut slots: Vec<i32> = self.items.iter().map(|item| item.slot as i32).collect();
        slots.sort_unstable();
        slots
    }
}
