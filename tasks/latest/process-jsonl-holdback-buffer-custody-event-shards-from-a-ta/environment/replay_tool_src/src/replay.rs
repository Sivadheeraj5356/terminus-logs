use std::collections::{BTreeMap, BTreeSet};

use crate::apply::apply_event;
use crate::reject::reject_reason;
use crate::types::{AuditRow, BufferState, EventRec, RejectRow};

pub struct ReplayOut {
    pub audit: Vec<AuditRow>,
    pub rejects: Vec<RejectRow>,
    pub duplicate_events: u64,
}

pub fn run_replay(
    buffers: &mut BTreeMap<String, BufferState>,
    events: Vec<EventRec>,
) -> ReplayOut {
    let mut seen = BTreeSet::new();
    let mut duplicate_events = 0u64;
    let mut audit = Vec::new();
    let mut rejects = Vec::new();

    for rec in events {
        let event = rec.event;
        if seen.contains(&event.event_id) {
            duplicate_events += 1;
            continue;
        }
        seen.insert(event.event_id.clone());
        if let Some(reason) = reject_reason(&event, buffers) {
            rejects.push(RejectRow {
                event_id: event.event_id,
                timestamp: event.timestamp,
                buffer_id: event.buffer_id,
                reason,
            });
            continue;
        }
        let applied_qty = apply_event(&event, buffers);
        audit.push(AuditRow {
            event_id: event.event_id,
            timestamp: event.timestamp,
            buffer_id: event.buffer_id,
            lane_id: event.lane_id.clone(),
            applied_qty,
        });
    }

    ReplayOut {
        audit,
        rejects,
        duplicate_events,
    }
}
