use crate::state::FacilityState;

pub fn assign_bed(
    state: &mut FacilityState,
    patient_id: &str,
    ward: &str,
    acuity: u8,
) -> Result<String, String> {
    if state.ward_at_capacity(ward) {
        return Err("ward_at_capacity".to_string());
    }

    let beds = state.available_beds_in_ward(ward, acuity);
    if beds.is_empty() {
        if ward_is_icu(state, ward) && acuity != 1 {
            return Err("icu_priority_violation".to_string());
        }
        return Err("no_available_bed".to_string());
    }

    let bed_id = beds[0].clone();
    state.bed_assignments.insert(bed_id.clone(), patient_id.to_string());
    *state.ward_occupancy.entry(ward.to_string()).or_insert(0) += 1;
    Ok(bed_id)
}

pub fn release_bed(state: &mut FacilityState, bed_id: &str) {
    if let Some(ward) = state.beds.get(bed_id).map(|b| b.ward.clone()) {
        state.bed_assignments.remove(bed_id);
        if let Some(occ) = state.ward_occupancy.get_mut(&ward) {
            *occ = occ.saturating_sub(1);
        }
    }
}

fn ward_is_icu(state: &FacilityState, ward: &str) -> bool {
    state
        .beds
        .values()
        .any(|b| b.ward == ward && b.is_icu)
}
