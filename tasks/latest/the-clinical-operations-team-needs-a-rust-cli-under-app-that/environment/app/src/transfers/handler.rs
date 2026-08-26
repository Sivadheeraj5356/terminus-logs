use crate::beds;
use crate::parser::{EventKind, HospitalEvent};
use crate::state::{FacilityState, RejectedEvent};

pub fn handle_transfer(state: &mut FacilityState, event: &HospitalEvent) -> bool {
    let EventKind::Transfer {
        patient_id,
        from_ward,
        to_ward,
        status,
        ..
    } = &event.kind
    else {
        return false;
    };

    if status == "pending" {
        return true;
    }

    let Some(patient) = state.patients.get(patient_id) else {
        state.rejected_events.push(RejectedEvent {
            event_id: event.event_id.clone(),
            event_time: event.event_time.clone(),
            event_seq: event.event_seq,
            reason: "unknown_patient".to_string(),
        });
        return false;
    };

    if patient.discharged {
        state.rejected_events.push(RejectedEvent {
            event_id: event.event_id.clone(),
            event_time: event.event_time.clone(),
            event_seq: event.event_seq,
            reason: "patient_discharged".to_string(),
        });
        return false;
    }

    let acuity = patient.acuity_level;
    if let Some(old_bed) = patient.bed_id.clone() {
        beds::release_bed(state, &old_bed);
    } else if let Some(ward) = patient.current_ward.as_ref() {
        let occ = state.ward_occupancy.entry(ward.clone()).or_insert(0);
        *occ = occ.saturating_sub(1);
    }

    match beds::assign_bed(state, patient_id, to_ward, acuity) {
        Ok(bed_id) => {
            let ward = state
                .beds
                .get(&bed_id)
                .map(|b| b.ward.clone())
                .unwrap_or_else(|| to_ward.clone());
            if let Some(p) = state.patients.get_mut(patient_id) {
                p.current_ward = Some(ward);
                p.bed_id = Some(bed_id);
            }
            let _ = from_ward;
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
