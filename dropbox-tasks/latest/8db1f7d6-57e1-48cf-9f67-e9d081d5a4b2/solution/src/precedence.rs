use crate::amount::{control_qty_ok, positive_qty};
use crate::types::EventIn;

pub fn early_reject(event: &EventIn) -> Option<&'static str> {
    let control = matches!(event.op.as_str(), "PAUSE" | "UNPAUSE");
    let transfer = event.op.as_str() == "TRANSFER";

    if !transfer && !event.peer_buffer_id.is_empty() {
        return Some("BAD_CONTROL");
    }
    if transfer && event.peer_buffer_id.is_empty() {
        return Some("BAD_CONTROL");
    }

    if control {
        if event.lane_id != "-" || !control_qty_ok(&event.qty) {
            return Some("BAD_CONTROL");
        }
    } else if !positive_qty(&event.qty).is_some() {
        return Some("BAD_QTY");
    } else if event.lane_id.is_empty() || event.lane_id == "-" {
        return Some("BAD_LANE");
    }
    None
}
