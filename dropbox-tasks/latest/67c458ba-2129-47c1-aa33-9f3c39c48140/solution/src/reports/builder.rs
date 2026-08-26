use crate::analytics;
use crate::state::FacilityState;

pub fn build_report(state: &FacilityState, as_of: &str) -> serde_json::Value {
    let mut rejected: Vec<_> = state
        .rejected_events
        .iter()
        .map(|r| {
            serde_json::json!({
                "event_id": r.event_id,
                "event_time": r.event_time,
                "event_seq": r.event_seq,
                "reason": r.reason,
            })
        })
        .collect();
    rejected.sort_by(|a, b| {
        let at = a["event_time"].as_str().unwrap_or("");
        let bt = b["event_time"].as_str().unwrap_or("");
        at.cmp(bt)
            .then(a["event_seq"].as_u64().cmp(&b["event_seq"].as_u64()))
            .then(a["event_id"].as_str().cmp(&b["event_id"].as_str()))
    });

    serde_json::json!({
        "as_of": as_of,
        "summary": analytics::build_summary(state, as_of),
        "patients": analytics::patient_rows(state, as_of),
        "ward_occupancy": analytics::ward_occupancy_at(state, as_of),
        "rejected_events": rejected,
    })
}
