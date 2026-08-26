use std::collections::BTreeMap;

use crate::amount::positive_qty;
use crate::precedence::early_reject;
use crate::types::{BufferState, EventIn};

pub fn reject_reason(event: &EventIn, buffers: &BTreeMap<String, BufferState>) -> Option<&'static str> {
    if let Some(reason) = early_reject(event) {
        return Some(reason);
    }

    let Some(state) = buffers.get(&event.buffer_id) else {
        return Some("UNKNOWN_BUFFER");
    };

    if event.op.as_str() == "TRANSFER" && !buffers.contains_key(&event.peer_buffer_id) {
        return Some("UNKNOWN_BUFFER");
    }

    let control = matches!(event.op.as_str(), "PAUSE" | "UNPAUSE");
    if control {
        if event.op == "PAUSE" && state.status == "HOLD" {
            return Some("BAD_CONTROL");
        }
        if event.op == "UNPAUSE" && state.status != "HOLD" {
            return Some("BAD_CONTROL");
        }
        return None;
    }

    let qty = positive_qty(&event.qty).unwrap_or(0);
    match event.op.as_str() {
        "INGEST" => {
            if state.status == "HOLD" {
                return Some("BUFFER_PAUSED");
            }
            if state.available() < qty {
                return Some("OVER_CAPACITY");
            }
        }
        "DISPATCH" => {
            if state.status == "HOLD" {
                return Some("BUFFER_PAUSED");
            }
            if state.holdback + state.filled < qty {
                return Some("OVER_CAPACITY");
            }
        }
        "HOLDBACK" => {
            if state.lane_filled(&event.lane_id) < qty {
                return Some("INSUFFICIENT_FILLED");
            }
        }
        "COMMIT" => {
            if state.lane_holdback(&event.lane_id) == 0 {
                return Some("INSUFFICIENT_HOLDBACK");
            }
        }
        "RELEASE" => {
            if state.lane_filled(&event.lane_id) == 0 {
                return Some("NOTHING_TO_RELEASE");
            }
        }
        "TRANSFER" => {
            let peer = buffers.get(&event.peer_buffer_id).unwrap();
            if state.status == "HOLD" || peer.status == "HOLD" {
                return Some("BUFFER_PAUSED");
            }
            if state.lane_holdback(&event.lane_id) < qty {
                return Some("INSUFFICIENT_HOLDBACK");
            }
            if peer.available() < qty {
                return Some("OVER_CAPACITY");
            }
        }
        _ => {}
    }

    None
}
