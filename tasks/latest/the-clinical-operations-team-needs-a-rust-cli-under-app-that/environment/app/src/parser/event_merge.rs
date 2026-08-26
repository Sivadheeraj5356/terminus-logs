use super::HospitalEvent;

pub fn merge_events(mut events: Vec<HospitalEvent>) -> Vec<HospitalEvent> {
    events.sort_by(|a, b| a.event_time.cmp(&b.event_time));
    events
}
