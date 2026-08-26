use std::collections::BTreeMap;

use crate::state::FacilityState;

pub fn ward_occupancy_at(state: &FacilityState, as_of: &str) -> Vec<serde_json::Value> {
    let mut counts: BTreeMap<String, u32> = BTreeMap::new();
    for patient in state.patients.values() {
        if patient.in_facility_at(as_of) {
            if let Some(ward) = &patient.current_ward {
                *counts.entry(ward.clone()).or_insert(0) += 1;
            }
        }
    }

    counts
        .into_iter()
        .map(|(ward, occupied)| {
            serde_json::json!({
                "ward": ward,
                "occupied": occupied,
                "capacity": state.ward_capacity.get(&ward).copied().unwrap_or(0),
            })
        })
        .collect()
}
