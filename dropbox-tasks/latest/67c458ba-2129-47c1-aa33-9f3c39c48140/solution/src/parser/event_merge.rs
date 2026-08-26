use super::HospitalEvent;

/// Sort events chronologically with deterministic tie-breaking and drop duplicates.
pub fn merge_events(mut events: Vec<HospitalEvent>) -> Vec<HospitalEvent> {
    events.sort_by(|a, b| {
        a.event_time
            .cmp(&b.event_time)
            .then(a.event_seq.cmp(&b.event_seq))
            .then(a.event_id.cmp(&b.event_id))
    });

    let mut merged = Vec::with_capacity(events.len());
    let mut seen = std::collections::HashSet::new();
    for event in events {
        if seen.insert(event.event_id.clone()) {
            merged.push(event);
        }
    }
    merged
}
