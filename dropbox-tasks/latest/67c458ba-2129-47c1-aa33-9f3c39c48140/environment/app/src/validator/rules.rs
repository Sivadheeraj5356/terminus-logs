use crate::admissions;
use crate::parser::{EventKind, HospitalEvent};
use crate::procedures;
use crate::state::FacilityState;
use crate::transfers;

pub fn validate_event_id(_state: &FacilityState, _event_id: &str) -> bool {
    true
}

pub fn process_event(state: &mut FacilityState, event: &HospitalEvent) {
    if !validate_event_id(state, &event.event_id) {
        return;
    }
    state.seen_event_ids.insert(event.event_id.clone());

    match &event.kind {
        EventKind::Admission { .. } => {
            admissions::handle_admission(state, event);
        }
        EventKind::Transfer { .. } => {
            transfers::handle_transfer(state, event);
        }
        EventKind::Procedure { .. } => {
            procedures::handle_procedure(state, event);
        }
        EventKind::Discharge {
            patient_id,
            disposition,
            ..
        } => handle_discharge(state, event, patient_id, disposition),
    }
}

fn handle_discharge(
    state: &mut FacilityState,
    event: &HospitalEvent,
    patient_id: &str,
    _disposition: &str,
) {
    let snapshot = state
        .patients
        .get(patient_id)
        .map(|p| (p.discharged, p.bed_id.clone()));

    let Some((already_discharged, bed_id)) = snapshot else {
        state.rejected_events.push(crate::state::RejectedEvent {
            event_id: event.event_id.clone(),
            event_time: event.event_time.clone(),
            event_seq: event.event_seq,
            reason: "unknown_patient".to_string(),
        });
        return;
    };

    if already_discharged {
        state.rejected_events.push(crate::state::RejectedEvent {
            event_id: event.event_id.clone(),
            event_time: event.event_time.clone(),
            event_seq: event.event_seq,
            reason: "already_discharged".to_string(),
        });
        return;
    }

    if let Some(bed_id) = bed_id {
        crate::beds::release_bed(state, &bed_id);
    }

    let patient = state.patients.get_mut(patient_id).expect("patient exists");
    patient.bed_id = None;
    patient.discharged = true;
    patient.discharge_time = Some(event.event_time.clone());
    patient.current_ward = None;
}
