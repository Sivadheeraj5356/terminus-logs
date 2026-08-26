use crate::beds;
use crate::parser::{EventKind, HospitalEvent};
use crate::state::{FacilityState, PatientRecord, RejectedEvent};

pub fn handle_admission(state: &mut FacilityState, event: &HospitalEvent) -> bool {
    let EventKind::Admission {
        patient_id,
        acuity_level,
        preferred_ward,
        ..
    } = &event.kind
    else {
        return false;
    };

    if state.patients.contains_key(patient_id) {
        state.rejected_events.push(RejectedEvent {
            event_id: event.event_id.clone(),
            event_time: event.event_time.clone(),
            event_seq: event.event_seq,
            reason: "duplicate_admission".to_string(),
        });
        return false;
    }

    let mut patient = PatientRecord::new(
        patient_id.clone(),
        *acuity_level,
        event.event_time.clone(),
    );

    let target_ward = if *acuity_level == 1 {
        let icu_beds = state.icu_beds_available();
        if !icu_beds.is_empty() {
            state
                .beds
                .get(&icu_beds[0])
                .map(|b| b.ward.clone())
                .unwrap_or_else(|| preferred_ward.clone())
        } else {
            preferred_ward.clone()
        }
    } else {
        preferred_ward.clone()
    };

    match beds::assign_bed(state, patient_id, &target_ward, *acuity_level) {
        Ok(bed_id) => {
            if let Some(bed) = state.beds.get(&bed_id) {
                patient.current_ward = Some(bed.ward.clone());
                patient.bed_id = Some(bed_id);
            }
            state.patients.insert(patient_id.clone(), patient);
            state.refresh_peak();
            true
        }
        Err(reason) => {
            state.rejected_events.push(RejectedEvent {
                event_id: event.event_id.clone(),
                event_time: event.event_time.clone(),
                event_seq: event.event_seq,
                reason,
            });
            false
        }
    }
}
