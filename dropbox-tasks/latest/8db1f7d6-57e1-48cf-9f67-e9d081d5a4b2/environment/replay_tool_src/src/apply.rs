use std::collections::BTreeMap;

use crate::amount::positive_qty;
use crate::types::{BufferState, EventIn};

pub fn apply_event(event: &EventIn, buffers: &mut BTreeMap<String, BufferState>) -> u64 {
    if event.op == "TRANSFER" {
        let qty = positive_qty(&event.qty).unwrap();
        let peer_id = event.peer_buffer_id.clone();
        let src_id = event.buffer_id.clone();
        let lane = event.lane_id.clone();
        let moved = buffers
            .get_mut(&src_id)
            .unwrap()
            .take_lane_holdback(&lane, qty);
        buffers
            .get_mut(&peer_id)
            .unwrap()
            .add_lane_filled(&lane, moved);
        return moved;
    }

    let state = buffers.get_mut(&event.buffer_id).unwrap();
    let lane = event.lane_id.clone();
    match event.op.as_str() {
        "INGEST" => {
            let qty = positive_qty(&event.qty).unwrap();
            state.add_lane_filled(&lane, qty);
            qty
        }
        "HOLDBACK" => {
            let qty = positive_qty(&event.qty).unwrap();
            state.add_lane_holdback(&lane, qty);
            qty
        }
        "DISPATCH" => {
            let qty = positive_qty(&event.qty).unwrap();
            let from_hold = state.take_holdback_lex(qty);
            let remain = qty.saturating_sub(from_hold);
            state.take_filled_lex(remain);
            state.dispatched += qty;
            qty
        }
        "COMMIT" => {
            let qty = positive_qty(&event.qty).unwrap();
            let take = qty.min(state.holdback);
            state.holdback -= take;
            state.filled += take;
            take
        }
        "RELEASE" => {
            let qty = positive_qty(&event.qty).unwrap();
            let take = qty.min(state.filled);
            state.filled -= take;
            take
        }
        "PAUSE" => {
            state.status = "HOLD".to_string();
            0
        }
        "UNPAUSE" => {
            state.status = "OPEN".to_string();
            0
        }
        _ => 0,
    }
}
